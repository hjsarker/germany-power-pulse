"""Build a static, real-data JSON snapshot for the GitHub Pages dashboard.

This command runs in GitHub Actions, not in the visitor's browser.
No fabricated fallback data is published if SMARD is unavailable.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from power_pulse.config import GENERATION, SERIES
from power_pulse.smard import load_market_data


def safe_float(value):
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return round(number, 5) if math.isfinite(number) else None


def generate(days=30, output=Path("docs/data/market.json")):
    frame, failures = load_market_data(days=days)
    if frame.empty:
        raise RuntimeError("SMARD returned no hourly observations.")
    if frame["price"].notna().sum() < 24:
        raise RuntimeError("Cannot publish a dashboard without at least 24 actual price observations.")
    if frame["grid_load"].notna().sum() < 24:
        raise RuntimeError("Cannot publish a dashboard without at least 24 actual grid-load observations.")
    if frame[list(GENERATION)].notna().sum().max() < 24:
        raise RuntimeError("Cannot publish a dashboard without actual generation observations.")

    frame = frame.sort_values("timestamp_utc")
    records = []
    for row in frame.to_dict(orient="records"):
        record = {"ts": pd.Timestamp(row["timestamp_utc"]).isoformat()}
        record.update({key: safe_float(row.get(key)) for key in SERIES})
        records.append(record)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Bundesnetzagentur | SMARD.de",
        "license": "CC BY 4.0",
        "resolution": "hour",
        "timezone": "Europe/Berlin",
        "dataset_days": days,
        "series_names": {key: spec.label for key, spec in SERIES.items()},
        "failed_series": failures,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    print(f"Written {len(records)} real observations; {frame['price'].notna().sum()} price hours; "
          f"{len(failures)} incomplete metrics to {output}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("docs/data/market.json"))
    args = parser.parse_args()
    generate(days=args.days, output=args.output)
