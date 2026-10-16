import numpy as np
import pandas as pd
from power_pulse.analytics import enrich, metrics, insight, validation_report
from power_pulse.config import GENERATION, RENEWABLE

def make_frame():
    df = pd.DataFrame({
        "timestamp_utc": pd.date_range("2026-04-01", periods=3, freq="h", tz="UTC"),
        "price": [10.0, -5.0, 15.0],
        "grid_load": [100.0] * 3,
    })
    for key in GENERATION:
        df[key] = 10.0
    return df

def test_renewable_share_and_negative_hours():
    result = metrics(enrich(make_frame()))
    assert abs(result["renewable_share"] - len(RENEWABLE) / len(GENERATION) * 100) < 1e-6
    assert result["negative_price_hours"] == 1
    assert result["hours_with_complete_generation"] == 3

def test_missing_values_not_counted_as_zero():
    df = make_frame()
    df.loc[0, "solar"] = np.nan
    enriched = enrich(df)
    assert pd.isna(enriched.loc[0, "renewable_pct"])
    assert metrics(enriched)["hours_with_complete_generation"] == 2
    report = validation_report(enriched)
    assert report.loc[report["Metric"] == "Solar", "Missing hours"].iloc[0] == 1

def test_daylight_saving_in_berlin():
    raw = pd.DataFrame({
        "timestamp_utc": pd.to_datetime(["2026-03-29T00:00Z", "2026-03-29T01:00Z"])
    })
    assert enrich(raw)["hour"].tolist() == [1, 3]

def test_insight_no_causation_claim_without_data():
    assert "Not enough" in insight(enrich(make_frame()))
