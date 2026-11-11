"""Customer and order records used by the pipeline."""

from dataclasses import dataclass

from parsing import normalize_date, normalize_money


@dataclass
class Customer:
    """One customer from the customer master file."""

    customer_id: str
    customer_name: str
    region: str
    signup_date: str

    @classmethod
    def from_row(cls, row):
        """Build a customer from one customers.csv row."""
        return cls(
            customer_id=row["customer_id"].strip(),
            customer_name=row["customer_name"].strip(),
            region=row["region"].strip(),
            signup_date=normalize_date(row["signup_date"]),
        )


@dataclass
class Order:
    """One clean order: the latest valid version of an order_id."""

    order_id: str
    order_date: str
    customer_id: str
    region: str
    product: str
    quantity: int
    unit_price: float
    revenue: float
    status: str
    source_file: str
    source_row: int

    @classmethod
    def from_row(cls, row, customers, source_file, source_row):
        """Build a clean order from a validated CSV row."""
        customer_id = row["customer_id"].strip()
        return cls(
            order_id=row["order_id"].strip(),
            order_date=normalize_date(row["order_date"]),
            customer_id=customer_id,
            region=customers[customer_id].region,
            product=row["product"].strip(),
            quantity=int(row["quantity"].strip()),
            unit_price=normalize_money(row["unit_price"]),
            revenue=normalize_money(row["revenue"]),
            status=row["status"].strip(),
            source_file=source_file,
            source_row=source_row,
        )


@dataclass
class StatusChange:
    """An order whose status changed in a later daily file."""

    order_id: str
    previous_status: str
    status: str
    source_file: str


@dataclass
class IngestResult:
    """Clean orders, rejected rows, and status changes from one ingest."""

    orders: list[Order]
    rejected_rows: list[dict]
    status_changes: list[StatusChange]
