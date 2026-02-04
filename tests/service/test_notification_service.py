"""Unit tests for NotificationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.models.pickup import Pickup
from src.app.services.notification_service import (
    LoggingNotificationProvider,
    NotificationService,
    NotificationStatus,
)


class TestNotificationService:
    """Test NotificationService business logic."""

    @pytest.fixture
    def mock_pickup(self):
        """Create a mock pickup for notification tests."""
        pickup = MagicMock(spec=Pickup)
        pickup.pickup_id = "pik_test123"
        pickup.contact_details = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1234567890",
        }
        pickup.pickup_window = {
            "start_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
        }
        return pickup

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_success(self, mock_pickup):
        """Test successful notification send."""
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)

        service = NotificationService(provider=mock_provider)
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.SENT
        mock_provider.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_no_email(self, mock_pickup):
        """Test notification skipped when no email."""
        mock_pickup.contact_details = {"name": "Test User"}

        service = NotificationService()
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.SKIPPED
        assert "No recipient email" in result.message

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_provider_failure(self, mock_pickup):
        """Test notification failure from provider."""
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=False)

        service = NotificationService(provider=mock_provider)
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_provider_exception(self, mock_pickup):
        """Test notification failure from provider exception."""
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(side_effect=Exception("Network error"))

        service = NotificationService(provider=mock_provider)
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.FAILED
        assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_empty_email(self, mock_pickup):
        """Test notification skipped when email is empty string."""
        mock_pickup.contact_details = {"name": "Test User", "email": ""}

        service = NotificationService()
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_send_pickup_reminder_null_contact_details(self, mock_pickup):
        """Test notification skipped when contact_details is None."""
        mock_pickup.contact_details = None

        service = NotificationService()
        result = await service.send_pickup_reminder(mock_pickup)

        assert result.status == NotificationStatus.SKIPPED


class TestLoggingNotificationProvider:
    """Test the development logging provider."""

    @pytest.mark.asyncio
    async def test_logging_provider_returns_true(self):
        """Test that logging provider always succeeds."""
        provider = LoggingNotificationProvider()
        result = await provider.send(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_logging_provider_with_different_inputs(self):
        """Test logging provider with various inputs."""
        provider = LoggingNotificationProvider()

        # Empty strings should still work
        result = await provider.send(
            recipient="",
            subject="",
            body="",
        )
        assert result is True

        # Long content should work
        result = await provider.send(
            recipient="user@example.com",
            subject="A" * 1000,
            body="B" * 10000,
        )
        assert result is True
