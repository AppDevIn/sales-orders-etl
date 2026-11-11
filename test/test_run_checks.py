"""Data-quality checks that run after the clean orders are loaded."""

import sqlite3

import pytest

from database import run_checks


def connection_with(rows):
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE fact_orders (
            order_id TEXT,
            order_date TEXT
        )
        """
    )
    connection.executemany(
        "INSERT INTO fact_orders (order_id, order_date) VALUES (?, ?)",
        rows,
    )
    return connection


def test_unique_december_orders_pass():
    connection = connection_with(
        [
            ("100001", "2025-12-01"),
            ("100002", "2025-12-31"),
        ]
    )
    run_checks(connection)


def test_duplicate_order_id_fails():
    connection = connection_with(
        [
            ("100001", "2025-12-01"),
            ("100001", "2025-12-02"),
        ]
    )
    with pytest.raises(ValueError, match=r"no duplicate order_id \(1 rows\)"):
        run_checks(connection)


def test_date_before_december_2025_fails():
    connection = connection_with([("100001", "2025-11-30")])
    with pytest.raises(ValueError, match=r"no dates outside December 2025 \(1 rows\)"):
        run_checks(connection)


def test_date_on_or_after_january_2026_fails():
    connection = connection_with([("100001", "2026-01-01")])
    with pytest.raises(ValueError, match=r"no dates outside December 2025 \(1 rows\)"):
        run_checks(connection)


def test_duplicate_is_reported_before_an_out_of_range_date():
    connection = connection_with(
        [
            ("100001", "2025-12-01"),
            ("100001", "2024-01-01"),
        ]
    )
    with pytest.raises(ValueError, match=r"no duplicate order_id \(1 rows\)"):
        run_checks(connection)
