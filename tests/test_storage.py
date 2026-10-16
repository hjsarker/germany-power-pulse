import sqlite3
import pandas as pd
from power_pulse.storage import save_sqlite, read_sqlite

def test_upsert_is_idempotent(tmp_path):
    db = tmp_path / "power_pulse.sqlite"
    frame = pd.DataFrame({
        "timestamp_utc": pd.to_datetime(["2026-02-01T00:00Z", "2026-02-01T01:00Z"]),
        "price": [50., -3.],
        "solar": [2000., None],
    })
    assert save_sqlite(frame, db) == 3
    assert save_sqlite(frame, db) == 3
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM energy_points").fetchone()[0] == 3
    restored = read_sqlite(db)
    assert restored["price"].tolist() == [50., -3.]
    assert pd.isna(restored["solar"].iloc[1])
