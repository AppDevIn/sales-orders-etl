"""Write the clean SQLite tables and run data-quality checks."""

import sqlite3
from dataclasses import asdict


def rebuild_database(database_path, customers, clean_orders, rejected_rows):
    """Atomically replace all output tables so repeated runs cannot double rows."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        drop_output_tables(connection)
        create_customers(connection)
        create_fact_orders(connection)
        create_rejected_orders(connection)
        insert_customers(connection, customers)
        insert_fact_orders(connection, clean_orders)
        insert_rejected_orders(connection, rejected_rows)
        create_daily_revenue(connection)
        passed_checks = run_checks(connection)
        return (*load_summary(connection), passed_checks)


def drop_output_tables(connection):
    """Remove the previous run's tables before recreating them."""
    connection.execute("DROP TABLE IF EXISTS daily_revenue_by_region")
    connection.execute("DROP TABLE IF EXISTS rejected_orders")
    connection.execute("DROP TABLE IF EXISTS fact_orders")
    connection.execute("DROP TABLE IF EXISTS customers")


def create_customers(connection):
    """Create the customer master table loaded from customers.csv."""
    connection.execute(
        """
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL,
            signup_date TEXT NOT NULL
        )
        """
    )


def insert_customers(connection, customers):
    """Load every customer from the master file."""
    connection.executemany(
        """
        INSERT INTO customers VALUES (
            :customer_id, :customer_name, :region, :signup_date
        )
        """,
        [asdict(customer) for customer in customers],
    )


def create_fact_orders(connection):
    """Create the clean order table."""
    connection.execute(
        """
        CREATE TABLE fact_orders (
            order_id TEXT PRIMARY KEY,
            order_date TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            region TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL,
            revenue REAL NOT NULL,
            status TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_row INTEGER NOT NULL
        )
        """
    )


def create_rejected_orders(connection):
    """Create the table that keeps invalid rows and why they were rejected."""
    connection.execute(
        """
        CREATE TABLE rejected_orders (
            source_file TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            order_id TEXT,
            order_date TEXT,
            customer_id TEXT,
            product TEXT,
            quantity TEXT,
            unit_price TEXT,
            revenue TEXT,
            status TEXT,
            rejection_reason TEXT NOT NULL,
            PRIMARY KEY (source_file, source_row)
        )
        """
    )


def insert_fact_orders(connection, clean_orders):
    """Load the latest valid version of each order."""
    connection.executemany(
        """
        INSERT INTO fact_orders VALUES (
            :order_id, :order_date, :customer_id, :region, :product,
            :quantity, :unit_price, :revenue, :status, :source_file, :source_row
        )
        """,
        [asdict(order) for order in clean_orders],
    )


def insert_rejected_orders(connection, rejected_rows):
    """Load each invalid row with its rejection reason."""
    connection.executemany(
        """
        INSERT INTO rejected_orders VALUES (
            :source_file, :source_row, :order_id, :order_date, :customer_id,
            :product, :quantity, :unit_price, :revenue, :status, :rejection_reason
        )
        """,
        rejected_rows,
    )


def create_daily_revenue(connection):
    """Aggregate completed-order revenue by date and region."""
    connection.execute(
        """
        CREATE TABLE daily_revenue_by_region AS
        SELECT
            order_date,
            region,
            COUNT(*) AS order_count,
            ROUND(SUM(revenue), 2) AS revenue
        FROM fact_orders
        WHERE status = 'Completed'
        GROUP BY order_date, region
        ORDER BY order_date, region
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX daily_revenue_date_region
        ON daily_revenue_by_region (order_date, region)
        """
    )


def load_summary(connection):
    """Return fact-row count, rejected-row count, and completed revenue."""
    fact_count = connection.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    rejected_count = connection.execute(
        "SELECT COUNT(*) FROM rejected_orders"
    ).fetchone()[0]
    completed_revenue = connection.execute(
        """
        SELECT ROUND(COALESCE(SUM(revenue), 0), 2)
        FROM fact_orders
        WHERE status = 'Completed'
        """
    ).fetchone()[0]
    return fact_count, rejected_count, completed_revenue


CHECKS = [
    (
        "no duplicate order_id in fact_orders",
        """
        SELECT COUNT(*) FROM (
            SELECT order_id FROM fact_orders
            GROUP BY order_id HAVING COUNT(*) > 1
        )
        """,
    ),
    (
        "no dates outside December 2025",
        """
        SELECT COUNT(*) FROM fact_orders
        WHERE order_date < '2025-12-01' OR order_date >= '2026-01-01'
        """,
    ),
    (
        "no quantity of 0 or less in fact_orders",
        "SELECT COUNT(*) FROM fact_orders WHERE quantity IS NULL OR quantity <= 0",
    ),
    (
        "revenue is stored as a number for every order",
        """
        SELECT COUNT(*) FROM fact_orders
        WHERE typeof(revenue) NOT IN ('real', 'integer')
        """,
    ),
    (
        "status is Pending, Completed or Cancelled",
        """
        SELECT COUNT(*) FROM fact_orders
        WHERE status NOT IN ('Pending', 'Completed', 'Cancelled')
        """,
    ),
    (
        "every fact_orders customer_id exists in customers",
        """
        SELECT COUNT(*) FROM fact_orders
        WHERE customer_id NOT IN (SELECT customer_id FROM customers)
        """,
    ),
    (
        "daily_revenue_by_region total matches Completed revenue in fact_orders",
        """
        SELECT CASE WHEN ABS(
            COALESCE((SELECT SUM(revenue) FROM daily_revenue_by_region), 0)
            - COALESCE(
                (SELECT SUM(revenue) FROM fact_orders WHERE status = 'Completed'), 0
            )
        ) > 0.05 THEN 1 ELSE 0 END
        """,
    ),
]


def run_checks(connection):
    """Stop the run if a data-quality guarantee is broken; return the passed checks."""
    passed = []
    for description, query in CHECKS:
        failure_count = connection.execute(query).fetchone()[0]
        if failure_count:
            raise ValueError(f"Check failed: {description} ({failure_count} rows)")
        passed.append(description)
    return passed
