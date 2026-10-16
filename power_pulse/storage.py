"""Local SQLite time-series storage and readback."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from .config import SERIES

SCHEMA = """
CREATE TABLE IF NOT EXISTS energy_points (
 timestamp_utc TEXT NOT NULL,
 metric TEXT NOT NULL,
 value REAL NOT NULL,
 source TEXT NOT NULL DEFAULT 'Bundesnetzagentur | SMARD.de',
 ingested_at_utc TEXT NOT NULL,
 PRIMARY KEY(timestamp_utc, metric)
);
CREATE INDEX IF NOT EXISTS idx_energy_metric_time
ON energy_points(metric, timestamp_utc);
"""

def save_sqlite(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = frame.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    loaded_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for metric in SERIES:
        if metric in df:
            for stamp, value in zip(df["timestamp_utc"], df[metric]):
                if pd.notna(value):
                    rows.append((stamp.isoformat(), metric, float(value), loaded_at))
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            """INSERT INTO energy_points(timestamp_utc, metric, value, ingested_at_utc)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(timestamp_utc, metric) DO UPDATE SET
              value=excluded.value, ingested_at_utc=excluded.ingested_at_utc""",
            rows,
        )
    return len(rows)

def read_sqlite(path, days=30):
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as conn:
        raw = pd.read_sql_query(
            "SELECT timestamp_utc, metric, value FROM energy_points ORDER BY timestamp_utc",
            conn)
    if raw.empty:
        return pd.DataFrame(columns=["timestamp_utc", *SERIES])
    wide = raw.pivot(index="timestamp_utc", columns="metric", values="value").reset_index()
    wide["timestamp_utc"] = pd.to_datetime(wide["timestamp_utc"], utc=True)
    cutoff = wide["timestamp_utc"].max() - pd.Timedelta(days=days)
    wide = wide.loc[wide["timestamp_utc"] >= cutoff].copy()
    for key in SERIES:
        if key not in wide:
            wide[key] = float("nan")
    return wide[["timestamp_utc", *SERIES]].sort_values(
        "timestamp_utc").reset_index(drop=True)
