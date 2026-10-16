from datetime import datetime, timezone
import pandas as pd
import pytest
from power_pulse.smard import SmardError, relevant_blocks, parse_series, fetch_metric, load_market_data

def test_blocks_overlap():
    day = 86400000
    assert relevant_blocks([0, 7 * day, 14 * day], 8 * day, 16 * day) == [7 * day, 14 * day]
    assert relevant_blocks([0, 7 * day], -day, -1) == []

def test_missing_api_values_remain_missing():
    parsed = parse_series({"series": [[1735689600000, 12.5], [1735693200000, None]]}, "price")
    assert parsed.iloc[0]["price"] == 12.5
    assert pd.isna(parsed.iloc[1]["price"])

def test_invalid_response_rejected():
    with pytest.raises(SmardError):
        parse_series({"unexpected": []}, "price")

def test_fetches_all_relevant_blocks(monkeypatch):
    day = 86400000
    start_block = 1735516800000
    calls = []
    def fake_json(url, session=None):
        calls.append(url)
        if "index_hour" in url:
            return {"timestamps": [start_block, start_block + day]}
        if url.endswith(f"_{start_block}.json"):
            return {"series": [[start_block, 10], [start_block + 12 * 3600000, 20]]}
        if url.endswith(f"_{start_block + day}.json"):
            return {"series": [[start_block + day, 30]]}
        raise AssertionError(url)
    monkeypatch.setattr("power_pulse.smard.fetch_json", fake_json)
    begin = datetime.fromtimestamp((start_block + 12 * 3600000) / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp((start_block + day) / 1000, tz=timezone.utc)
    df = fetch_metric("solar", begin, end)
    assert df["solar"].tolist() == [20., 30.]
    assert len(calls) == 3

def test_upstream_failure_not_fabricated(monkeypatch):
    def fake_fetch(key, start, end, session=None):
        if key == "price":
            raise SmardError("Upstream unavailable")
        return pd.DataFrame({
            "timestamp_utc": pd.date_range(start, end, freq="h", tz="UTC"),
            key: 100.
        })
    monkeypatch.setattr("power_pulse.smard.fetch_metric", fake_fetch)
    now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
    df, failures = load_market_data(days=1, now=now, keys=("price", "solar"))
    assert len(df) == 24
    assert df["price"].isna().all()
    assert df["solar"].eq(100.).all()
    assert "price" in failures
