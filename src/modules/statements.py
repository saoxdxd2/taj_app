"""Shared period handling for customer and supplier account statements.

A statement folds every movement before the requested start into a single
opening balance, then lists each debit/credit with a running balance.
"""
from datetime import date, datetime, time, timezone
from typing import Optional, Tuple


def as_naive_utc(value):
    """Normalizes a UI date/datetime to the naive UTC SQLite stores."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return datetime.combine(value, time.min)


def statement_bounds(date_from=None, date_to=None) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Returns the inclusive [start, end] bounds for a statement period.

    A plain date end means 'the whole day', so a movement stored at 14:30
    still belongs to that day's statement.
    """
    start = as_naive_utc(date_from)
    if date_to is None:
        end = None
    elif isinstance(date_to, datetime):
        end = as_naive_utc(date_to)
    else:
        end = datetime.combine(date_to, time.max)

    if start is not None and end is not None and start > end:
        raise ValueError("The start date must not be after the end date.")
    return start, end
