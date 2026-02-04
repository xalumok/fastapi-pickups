"""Unit tests for datetime utilities."""

from datetime import UTC, datetime, timezone

import pytest

from src.app.core.utils.datetime import parse_iso_datetime


class TestParseIsoDatetime:
    """Test parse_iso_datetime utility function."""

    def test_parse_none_returns_none(self):
        """Test parsing None returns None."""
        assert parse_iso_datetime(None) is None

    def test_parse_valid_zulu_time(self):
        """Test parsing Zulu time string."""
        result = parse_iso_datetime("2024-01-15T10:30:00Z")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo is not None

    def test_parse_valid_offset_time(self):
        """Test parsing offset time string."""
        result = parse_iso_datetime("2024-01-15T10:30:00+00:00")

        assert result is not None
        assert result.tzinfo is not None

    def test_parse_positive_offset(self):
        """Test parsing positive offset time string."""
        result = parse_iso_datetime("2024-01-15T10:30:00+05:30")

        assert result is not None
        assert result.hour == 10
        assert result.tzinfo is not None

    def test_parse_negative_offset(self):
        """Test parsing negative offset time string."""
        result = parse_iso_datetime("2024-01-15T10:30:00-08:00")

        assert result is not None
        assert result.hour == 10
        assert result.tzinfo is not None

    def test_parse_with_microseconds(self):
        """Test parsing datetime with microseconds."""
        result = parse_iso_datetime("2024-01-15T10:30:00.123456Z")

        assert result is not None
        assert result.microsecond == 123456

    def test_parse_with_milliseconds(self):
        """Test parsing datetime with milliseconds."""
        result = parse_iso_datetime("2024-01-15T10:30:00.123Z")

        assert result is not None
        assert result.microsecond == 123000

    def test_parse_naive_datetime_object(self):
        """Test parsing naive datetime adds UTC."""
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        result = parse_iso_datetime(naive_dt)

        assert result is not None
        assert result.tzinfo == UTC

    def test_parse_aware_datetime_object(self):
        """Test parsing aware datetime is passed through."""
        aware_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = parse_iso_datetime(aware_dt)

        assert result is aware_dt

    def test_parse_aware_datetime_other_timezone(self):
        """Test parsing aware datetime with non-UTC timezone."""
        other_tz = timezone.utc  # Using UTC for simplicity
        aware_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=other_tz)
        result = parse_iso_datetime(aware_dt)

        assert result is aware_dt
        assert result.tzinfo is not None

    def test_parse_invalid_string_returns_none(self):
        """Test parsing invalid string returns None."""
        assert parse_iso_datetime("not-a-date") is None

    def test_parse_empty_string_returns_none(self):
        """Test parsing empty string returns None."""
        assert parse_iso_datetime("") is None

    def test_parse_integer_returns_none(self):
        """Test parsing integer returns None."""
        assert parse_iso_datetime(12345) is None

    def test_parse_list_returns_none(self):
        """Test parsing list returns None."""
        assert parse_iso_datetime(["2024-01-15"]) is None

    def test_parse_dict_returns_none(self):
        """Test parsing dict returns None."""
        assert parse_iso_datetime({"date": "2024-01-15"}) is None

    def test_parse_float_returns_none(self):
        """Test parsing float returns None."""
        assert parse_iso_datetime(1705312200.0) is None

    def test_parse_naive_string(self):
        """Test parsing naive string adds UTC."""
        result = parse_iso_datetime("2024-01-15T10:30:00")

        assert result is not None
        assert result.tzinfo is not None

    def test_parse_date_only(self):
        """Test parsing date-only string."""
        result = parse_iso_datetime("2024-01-15")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_partial_time(self):
        """Test parsing partial time string."""
        result = parse_iso_datetime("2024-01-15T10:30")

        assert result is not None
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0

    def test_parse_preserves_date_components(self):
        """Test that all date components are preserved."""
        result = parse_iso_datetime("2024-12-31T23:59:59Z")

        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
