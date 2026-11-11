"""Normalize raw CSV values and check file schemas."""

from datetime import datetime


def normalize_date(value):
    """Convert ISO or day/month dates to ISO format."""
    value = value.strip()
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Unsupported order date: {value!r}")


def normalize_money(value):
    """Convert values such as '$1,234.00' to a number."""
    try:
        return float(value.strip().replace("$", "").replace(",", ""))
    except ValueError as error:
        raise ValueError(f"Invalid money value: {value!r}") from error


def check_columns(path, actual_columns, expected_columns):
    """Fail clearly if an input schema changes unexpectedly."""
    if actual_columns != expected_columns:
        raise ValueError(
            f"Unexpected columns in {path.name}: "
            f"expected {expected_columns}, got {actual_columns}"
        )
