"""Data-quality checks that run after the clean orders are loaded."""

import sqlite3

import pytest

from database import CHECKS, create_daily_revenue, run_checks


DEFAULT_ORDER = {
    "order_id": "100001",
    "order_date": "2025-12-01",
    "customer_id": "C001",
    "region": "East",
    "product": "Monitor",
    "quantity": 1,
    "unit_price": 100.0,
    "revenue": 100.0,
    "status": "Completed",
    "source_file": "orders_2025-12-01.csv",
    "source_row": 2,
}


def connection_with(orders, customer_ids=("C001",)):
    """Build an in-memory database with the output schema but no constraints.

    Constraints are left out on purpose so that each check can be exercised
    on bad data instead of the INSERT failing first.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE customers (
            customer_id TEXT, customer_name TEXT, region TEXT, signup_date TEXT
        )
        """
    )
    connection.executemany(
        "INSERT INTO customers VALUES (?, 'Name', 'East', '2024-01-01')",
        [(customer_id,) for customer_id in customer_ids],
    )
    connection.execute(
        """
        CREATE TABLE fact_orders (
            order_id TEXT, order_date TEXT, customer_id TEXT, region TEXT,
            product TEXT, quantity INTEGER, unit_price REAL, revenue REAL,
            status TEXT, source_file TEXT, source_row INTEGER
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO fact_orders VALUES (
            :order_id, :order_date, :customer_id, :region, :product,
            :quantity, :unit_price, :revenue, :status, :source_file, :source_row
        )
        """,
        [{**DEFAULT_ORDER, **order} for order in orders],
    )
    create_daily_revenue(connection)
    return connection


def test_clean_data_passes_every_check():
    connection = connection_with(
        [
            {"order_id": "100001", "order_date": "2025-12-01"},
            {"order_id": "100002", "order_date": "2025-12-31", "status": "Pending"},
        ]
    )
    assert run_checks(connection) == [description for description, _ in CHECKS]


def test_duplicate_order_id_fails():
    connection = connection_with(
        [
            {"order_id": "100001", "order_date": "2025-12-01"},
            {"order_id": "100001", "order_date": "2025-12-02"},
        ]
    )
    with pytest.raises(ValueError, match=r"no duplicate order_id in fact_orders \(1 rows\)"):
        run_checks(connection)


def test_date_before_december_2025_fails():
    connection = connection_with([{"order_date": "2025-11-30"}])
    with pytest.raises(ValueError, match=r"no dates outside December 2025 \(1 rows\)"):
        run_checks(connection)


def test_date_on_or_after_january_2026_fails():
    connection = connection_with([{"order_date": "2026-01-01"}])
    with pytest.raises(ValueError, match=r"no dates outside December 2025 \(1 rows\)"):
        run_checks(connection)


def test_non_positive_quantity_fails():
    connection = connection_with([{"quantity": 0}])
    with pytest.raises(ValueError, match=r"no quantity of 0 or less"):
        run_checks(connection)


def test_text_revenue_fails():
    connection = connection_with([{"revenue": "$100.00"}])
    with pytest.raises(ValueError, match=r"revenue is stored as a number"):
        run_checks(connection)


def test_unknown_status_fails():
    connection = connection_with([{"status": "Shipped"}])
    with pytest.raises(ValueError, match=r"status is Pending, Completed or Cancelled"):
        run_checks(connection)


def test_unknown_customer_fails():
    connection = connection_with([{"customer_id": "C999"}])
    with pytest.raises(ValueError, match=r"customer_id exists in customers"):
        run_checks(connection)


def test_aggregate_mismatch_fails():
    connection = connection_with([{"revenue": 100.0}])
    connection.execute("UPDATE daily_revenue_by_region SET revenue = revenue + 1")
    with pytest.raises(ValueError, match=r"daily_revenue_by_region total matches"):
        run_checks(connection)


def test_duplicate_is_reported_before_an_out_of_range_date():
    connection = connection_with(
        [
            {"order_id": "100001", "order_date": "2025-12-01"},
            {"order_id": "100001", "order_date": "2024-01-01"},
        ]
    )
    with pytest.raises(ValueError, match=r"no duplicate order_id in fact_orders \(1 rows\)"):
        run_checks(connection)
