"""Download official SMARD hourly electricity observations without API keys."""
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import BASE_URL, SERIES, RESOLUTION


class SmardError(RuntimeError):
    """Upstream network or data error."""


def make_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=.6,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "GermanyPowerPulse/0.1 portfolio"})
    return session


def fetch_json(url, session=None):
    client = session or make_session()
    try:
        response = client.get(url, timeout=(8, 20))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SmardError(f"SMARD request failed at {url}: {exc}") from exc
    finally:
        if session is None:
            client.close()
    if not isinstance(payload, dict):
        raise SmardError(f"Invalid API response at {url}")
    return payload


def relevant_blocks(timestamps, start_ms, end_ms):
    blocks = sorted(set(map(int, timestamps)))
    if not blocks or end_ms < blocks[0]:
        return []
    position = max(0, bisect_right(blocks, start_ms) - 1)
    return [x for x in blocks[position:] if x <= end_ms]


def parse_series(payload, label):
    series = payload.get("series")
    if not isinstance(series, list):
        raise SmardError(f"{label}: missing 'series' array")
    rows = []
    for entry in series:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        try:
            stamp = int(entry[0])
            value = float(entry[1]) if entry[1] is not None else float("nan")
        except (ValueError, TypeError, OverflowError):
            continue
        rows.append((stamp, value))
    if not rows:
        return pd.DataFrame(columns=["timestamp_utc", label])
    frame = pd.DataFrame(rows, columns=["timestamp_ms", label])
    frame["timestamp_utc"] = pd.to_datetime(
        frame.pop("timestamp_ms"), unit="ms", utc=True)
    return (frame.sort_values("timestamp_utc")
            .drop_duplicates("timestamp_utc", keep="last")
            [["timestamp_utc", label]].reset_index(drop=True))


def fetch_metric(key, start, end, session=None):
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Supply increasing timezone-aware UTC boundaries")
    spec = SERIES[key]
    base = f"{BASE_URL}/{spec.filter_id}/{spec.region}"
    own_session = session is None
    client = session or make_session()
    try:
        index = fetch_json(f"{base}/index_{RESOLUTION}.json", client)
        blocks = relevant_blocks(
            index.get("timestamps", []),
            int(start.timestamp() * 1000),
            int(end.timestamp() * 1000),
        )
        if not blocks:
            raise SmardError(f"No indexed blocks for {key}")
        pieces = [
            parse_series(fetch_json(
                f"{base}/{spec.filter_id}_{spec.region}_{RESOLUTION}_{block}.json",
                client), key)
            for block in blocks
        ]
        frame = pd.concat(pieces, ignore_index=True)
    finally:
        if own_session:
            client.close()
    if frame.empty:
        raise SmardError(f"No observations found for {key}")
    frame = frame.drop_duplicates("timestamp_utc", keep="last")
    return frame.loc[
        frame["timestamp_utc"].between(pd.Timestamp(start), pd.Timestamp(end))
    ].reset_index(drop=True)


def load_market_data(days=14, *, now=None, keys=None, max_workers=6):
    """Fetch complete UTC hourly grid; preserve unavailable observations as NaN."""
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    start = end - timedelta(days=days) + timedelta(hours=1)
    fields = tuple(keys) if keys is not None else tuple(SERIES)
    if set(fields) - set(SERIES):
        raise ValueError("Unknown SMARD metrics")
    frame = pd.DataFrame({
        "timestamp_utc": pd.date_range(start, end, freq="h", tz="UTC")
    })
    failures = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = {pool.submit(fetch_metric, key, start, end): key for key in fields}
        for task in as_completed(tasks):
            key = tasks[task]
            try:
                frame = frame.merge(task.result(), on="timestamp_utc",
                                    how="left", validate="one_to_one")
            except (SmardError, requests.RequestException, ValueError, KeyError) as exc:
                failures[key] = str(exc)
                frame[key] = float("nan")
    return frame[["timestamp_utc", *fields]].sort_values(
        "timestamp_utc").reset_index(drop=True), failures
