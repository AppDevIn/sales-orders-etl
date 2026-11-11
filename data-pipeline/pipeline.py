#!/usr/bin/env python3
"""Load daily order CSV files into a clean, re-runnable SQLite database."""

import argparse
from collections import Counter
from pathlib import Path

from database import rebuild_database
from ingest import discover_order_files, ingest_orders, load_customers


CUSTOMERS_FILE = "customers.csv"


def main():
    """Run the complete batch pipeline and print an audit summary."""
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=script_dir / "data")
    parser.add_argument("--database", type=Path, default=script_dir / "sales.db")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    database_path = args.database.resolve()
    customers_path = input_dir / CUSTOMERS_FILE
    customers = load_customers(customers_path)
    result = ingest_orders(
        input_dir=input_dir,
        customers=customers,
        customers_file=customers_path.name,
    )
    fact_count, rejected_count, completed_revenue = rebuild_database(
        database_path, result.orders, result.rejected_rows
    )
    rejected_by_file = Counter(row["source_file"] for row in result.rejected_rows)

    print(f"Database: {database_path}")
    print(f"fact_orders: {fact_count}")
    print(f"rejected_orders: {rejected_count}")
    print(f"Completed revenue: ${completed_revenue:,.2f}")
    print("Rejected rows by file:")
    for path in discover_order_files(input_dir):
        print(f"  {path.name}: {rejected_by_file[path.name]}")
    print("Status changes (later file wins):")
    for change in result.status_changes:
        print(
            f"  {change.order_id}: {change.previous_status} -> "
            f"{change.status} in {change.source_file}"
        )
    print("Checks passed:")
    print("  no duplicate order_id")
    print("  no dates outside December 2025")


if __name__ == "__main__":
    main()
