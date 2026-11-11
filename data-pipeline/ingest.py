"""Read customer and daily order CSV files."""

import csv
import re
from datetime import datetime

from models import Customer, IngestResult, Order, StatusChange
from parsing import check_columns


ORDER_COLUMNS = [
    "order_id",
    "order_date",
    "customer_id",
    "product",
    "quantity",
    "unit_price",
    "revenue",
    "status",
]
CUSTOMER_COLUMNS = ["customer_id", "customer_name", "region", "signup_date"]
ORDER_FILE_PATTERN = re.compile(r"orders_(\d{4}-\d{2}-\d{2})\.csv$")


def load_customers(path):
    """Load the customer master keyed by customer_id."""
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        check_columns(path, reader.fieldnames, CUSTOMER_COLUMNS)
        customers = {
            customer.customer_id: customer
            for customer in (Customer.from_row(row) for row in reader)
        }
    if not customers:
        raise ValueError(f"{path.name} is empty")
    return customers


def discover_order_files(input_dir):
    """Find and chronologically sort every orders_YYYY-MM-DD.csv file."""
    dated_files = []
    for path in input_dir.glob("orders_*.csv"):
        match = ORDER_FILE_PATTERN.fullmatch(path.name)
        if match:
            datetime.strptime(match.group(1), "%Y-%m-%d")
            dated_files.append((match.group(1), path))
    if not dated_files:
        raise ValueError(f"No orders_YYYY-MM-DD.csv files found in {input_dir}")
    return [path for _, path in sorted(dated_files)]


def validate_row(row, customer_ids, customers_file):
    """Return every business-rule rejection reason for one raw row."""
    reasons = []
    if not row["order_id"].strip():
        reasons.append("missing order_id")
    try:
        quantity = int(row["quantity"].strip())
        if quantity <= 0:
            reasons.append("quantity must be greater than 0")
    except ValueError:
        reasons.append("quantity must be an integer greater than 0")
    if row["customer_id"].strip() not in customer_ids:
        reasons.append(f"customer_id not found in {customers_file}")
    return reasons


def ingest_orders(*, input_dir, customers, customers_file):
    """Validate rows and keep the latest valid version of each order_id."""
    latest_orders = {}
    rejected_rows = []
    status_changes = []

    for path in discover_order_files(input_dir):
        with path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            check_columns(path, reader.fieldnames, ORDER_COLUMNS)

            for source_row, row in enumerate(reader, start=2):
                reasons = validate_row(row, set(customers), customers_file)
                if reasons:
                    rejected_rows.append(
                        {
                            "source_file": path.name,
                            "source_row": source_row,
                            **{column: row[column].strip() for column in ORDER_COLUMNS},
                            "rejection_reason": "; ".join(reasons),
                        }
                    )
                    continue

                order = Order.from_row(row, customers, path.name, source_row)
                previous = latest_orders.get(order.order_id)
                status_changed = (
                    previous
                    and previous.source_file != path.name
                    and previous.status != order.status
                )
                if status_changed:
                    status_changes.append(
                        StatusChange(
                            order_id=order.order_id,
                            previous_status=previous.status,
                            status=order.status,
                            source_file=path.name,
                        )
                    )
                latest_orders[order.order_id] = order

    return IngestResult(
        orders=list(latest_orders.values()),
        rejected_rows=rejected_rows,
        status_changes=status_changes,
    )
