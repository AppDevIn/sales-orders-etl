"""Business rules for one order row."""

from ingest import validate_row


CUSTOMERS = {"C001", "C002"}
CUSTOMERS_FILE = "customers.csv"


def order_row(**overrides):
    row = {
        "order_id": "100001",
        "order_date": "2025-12-01",
        "customer_id": "C001",
        "product": "Monitor",
        "quantity": "2",
        "unit_price": "10.00",
        "revenue": "20.00",
        "status": "Completed",
    }
    row.update(overrides)
    return row


def reasons_for(**overrides):
    return validate_row(order_row(**overrides), CUSTOMERS, CUSTOMERS_FILE)


def test_valid_row_has_no_rejection_reasons():
    assert reasons_for() == []


def test_missing_order_id_is_rejected():
    assert reasons_for(order_id="  ") == ["missing order_id"]


def test_zero_quantity_is_rejected():
    assert reasons_for(quantity="0") == ["quantity must be greater than 0"]


def test_negative_quantity_is_rejected():
    assert reasons_for(quantity="-3") == ["quantity must be greater than 0"]


def test_non_integer_quantity_is_rejected():
    assert reasons_for(quantity="1.5") == [
        "quantity must be an integer greater than 0"
    ]


def test_unknown_customer_is_rejected():
    assert reasons_for(customer_id="C999") == [
        "customer_id not found in customers.csv"
    ]


def test_row_can_fail_every_rule_at_once():
    assert reasons_for(order_id="", quantity="0", customer_id="C999") == [
        "missing order_id",
        "quantity must be greater than 0",
        "customer_id not found in customers.csv",
    ]


def test_blank_order_id_and_bad_quantity_are_both_reported():
    assert reasons_for(order_id=" ", quantity="abc") == [
        "missing order_id",
        "quantity must be an integer greater than 0",
    ]
