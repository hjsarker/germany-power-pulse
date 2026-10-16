"""Descriptive analytics and reproducible data-quality metrics."""
import numpy as np
import pandas as pd
from .config import CONVENTIONAL, GENERATION, RENEWABLE, SERIES, TIME_ZONE


def enrich(raw):
    df = raw.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    for key in SERIES:
        if key not in df:
            df[key] = np.nan
        df[key] = pd.to_numeric(df[key], errors="coerce")
    df["local_time"] = df["timestamp_utc"].dt.tz_convert(TIME_ZONE)
    df["day"] = df["local_time"].dt.date
    df["hour"] = df["local_time"].dt.hour
    df["generation_complete"] = df[list(GENERATION)].notna().all(axis=1)
    df["renewable_mwh"] = df[list(RENEWABLE)].sum(axis=1, min_count=len(RENEWABLE))
    df["conventional_mwh"] = df[list(CONVENTIONAL)].sum(axis=1, min_count=len(CONVENTIONAL))
    df["generation_mwh"] = df[list(GENERATION)].sum(axis=1, min_count=len(GENERATION))
    df["wind_solar_mwh"] = df[
        ["wind_onshore", "wind_offshore", "solar"]
    ].sum(axis=1, min_count=3)
    df["renewable_pct"] = np.where(
        df["generation_complete"] & df["generation_mwh"].gt(0),
        df["renewable_mwh"] / df["generation_mwh"] * 100, np.nan)
    return df


def metrics(df):
    prices = df["price"].dropna()
    mix = df.loc[df["generation_complete"]]
    renewable = mix["renewable_mwh"].sum()
    total = mix["generation_mwh"].sum()
    return {
        "average_price": float(prices.mean()) if len(prices) else None,
        "negative_price_hours": int(prices.lt(0).sum()) if len(prices) else None,
        "renewable_share": float(renewable / total * 100) if total > 0 else None,
        "grid_load_gwh": float(df["grid_load"].sum(min_count=1) / 1000)
        if df["grid_load"].notna().any() else None,
        "hours": len(df),
        "hours_with_price": len(prices),
        "hours_with_complete_generation": len(mix),
    }


def validation_report(df):
    rows = []
    for key, spec in SERIES.items():
        available = df[key].notna()
        rows.append({
            "Metric": spec.label,
            "Coverage (%)": round(float(available.mean() * 100), 1) if len(df) else 0,
            "Available hours": int(available.sum()),
            "Missing hours": int((~available).sum()),
            "Negative non-price values": int(df[key].lt(0).sum()) if key != "price" else 0,
        })
    return pd.DataFrame(rows)


def insight(df):
    valid = df.dropna(subset=["price", "wind_solar_mwh", "grid_load"])
    if len(valid) < 24:
        return "Not enough complete observations to compare generation and prices."
    low_q, high_q = valid["wind_solar_mwh"].quantile([.25, .75])
    low = valid.loc[valid["wind_solar_mwh"] <= low_q, "price"]
    high = valid.loc[valid["wind_solar_mwh"] >= high_q, "price"]
    if low.empty or high.empty:
        return "Not enough variation in wind and solar output for this comparison."
    difference = high.mean() - low.mean()
    trend = "lower" if difference < 0 else "higher"
    return (f"During this period mean day-ahead prices were €{abs(difference):.1f}/MWh "
            f"{trend} in high wind/solar output hours (top quartile) than low output "
            "hours (bottom quartile). This association does not establish causation.")
