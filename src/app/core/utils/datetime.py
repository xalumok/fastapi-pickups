"""Datetime utilities for consistent parsing and handling."""

from datetime import UTC, datetime

from dateutil.parser import isoparse


def parse_iso_datetime(value: str | datetime | None) -> datetime | None:
    """
    Parse an ISO 8601 datetime string into a timezone-aware datetime.

    Uses python-dateutil's isoparse for robust ISO 8601 parsing.

    Args:
        value: An ISO 8601 datetime string, a datetime object, or None.

    Returns:
        A timezone-aware datetime in UTC, or None if parsing fails.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    if not isinstance(value, str):
        return None

    try:
        dt = isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None
