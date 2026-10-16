"""Collect SMARD observations into an optional local SQLite snapshot."""
import argparse
from pathlib import Path
from power_pulse.smard import load_market_data
from power_pulse.storage import save_sqlite

def main():
    parser = argparse.ArgumentParser(description="Refresh German energy observations")
    parser.add_argument("--days", type=int, default=30, choices=(7, 14, 30, 60, 90))
    parser.add_argument("--db", type=Path, default=Path("data/power_pulse.sqlite"))
    args = parser.parse_args()
    frame, failures = load_market_data(days=args.days)
    count = save_sqlite(frame, args.db)
    print(f"Stored {count:,} observations in {args.db}")
    if failures:
        for metric, error in failures.items():
            print(f"WARNING {metric}: {error}")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
