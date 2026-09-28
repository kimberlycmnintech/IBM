"""
detect.py
CLI entry point — loads a transaction CSV, scores accounts, and prints a Rich table.

Usage
-----
    python detect.py
    python detect.py --csv path/to/transactions.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from mule_detector.scoring import score_accounts
from mule_detector.report import render_table


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect money mule accounts in a transaction CSV."
    )
    parser.add_argument(
        "--csv",
        default=str(Path(__file__).parent / "data" / "transactions.csv"),
        help="Path to the transaction CSV file (default: data/transactions.csv)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
        print("Run 'python generate_mock_data.py' to generate sample data.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    results = score_accounts(df)
    render_table(results)


if __name__ == "__main__":
    main()
