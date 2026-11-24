"""Build the analytical tables: load -> clean -> build -> parquet.

Usage:
    python scripts/build_data.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.build import PROCESSED_DIR, build_tables, save_tables  # noqa: E402
from src.clean import clean_all  # noqa: E402
from src.load import load_raw  # noqa: E402


def main() -> None:
    start = time.perf_counter()
    print("1/3  Loading raw CSV files ...")
    raw = load_raw()
    for name, df in raw.items():
        print(f"     {name:<22} {len(df):>9,} rows")

    print("\n2/3  Cleaning ...")
    clean, report = clean_all(raw)
    print(report)

    print("\n3/3  Building analytical tables ...")
    tables = build_tables(clean)
    save_tables(tables)
    meta = tables["meta"]
    print(f"     Complete period: {meta['first_month']} -> {meta['last_month']}")
    excluded = ", ".join(f"{m['month']} ({m['orders']} orders)" for m in meta["excluded_months"])
    print(
        f"     Excluded incomplete months (< 10% of median {meta['median_monthly_orders']:,}"
        f" orders): {excluded}"
    )
    for name, n in meta["rows"].items():
        print(f"     {name:<22} {n:>9,} rows")
    print(f"\nDone in {time.perf_counter() - start:.1f}s -> {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
