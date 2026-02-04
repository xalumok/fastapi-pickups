"""Unit tests for PickupService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.models.pickup import Pickup
from src.app.services.pickup_service import PickupService


class TestPickupServiceValidation:
    """Test PickupService validation logic."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_pickup(self):
        """Create a mock pickup object."""
        pickup = MagicMock(spec=Pickup)
        pickup.pickup_id = "pik_test123"
        pickup.is_deleted = False
        pickup.notification_sent = False
        pickup.pickup_window = {
            "start_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
        }
        pickup.contact_details = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1234567890",
        }
        return pickup

    @pytest.mark.asyncio
    async def test_get_active_pickup_found(self, mock_session, mock_pickup):
        """Test retrieving an active pickup."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.get_active_pickup("pik_test123")

        assert result == mock_pickup
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_pickup_not_found(self, mock_session):
        """Test retrieving a non-existent pickup."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.get_active_pickup("pik_nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_for_notification_valid(self, mock_session, mock_pickup):
        """Test validation for a valid pickup."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_test123")

        assert result.is_valid is True
        assert result.pickup == mock_pickup
        assert result.skip_reason is None

    @pytest.mark.asyncio
    async def test_validate_for_notification_not_found(self, mock_session):
        """Test validation when pickup not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_nonexistent")

        assert result.is_valid is False
        assert result.pickup is None
        assert result.skip_reason == "pickup_not_found_or_cancelled"

    @pytest.mark.asyncio
    async def test_validate_for_notification_already_sent(
        self, mock_session, mock_pickup
    ):
        """Test validation when notification already sent."""
        mock_pickup.notification_sent = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_test123")

        assert result.is_valid is False
        assert result.skip_reason == "notification_already_sent"

    @pytest.mark.asyncio
    async def test_validate_for_notification_window_passed(
        self, mock_session, mock_pickup
    ):
        """Test validation when pickup window has passed."""
        mock_pickup.pickup_window = {
            "start_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
            "end_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_test123")

        assert result.is_valid is False
        assert result.skip_reason == "pickup_window_passed"

    @pytest.mark.asyncio
    async def test_validate_for_notification_invalid_window_format(
        self, mock_session, mock_pickup
    ):
        """Test validation with invalid pickup window format."""
        mock_pickup.pickup_window = {"start_at": "invalid-date"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_test123")

        # Should still be valid (warning logged but not blocking)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_for_notification_no_pickup_window(
        self, mock_session, mock_pickup
    ):
        """Test validation with no pickup window."""
        mock_pickup.pickup_window = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.validate_for_notification("pik_test123")

        # Should still be valid when no window is set
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_mark_notification_sent(self, mock_session, mock_pickup):
        """Test marking notification as sent."""
        service = PickupService(mock_session)
        await service.mark_notification_sent(mock_pickup)

        assert mock_pickup.notification_sent is True
        mock_session.commit.assert_called_once()


class TestPickupServiceCRUD:
    """Test PickupService CRUD operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_pickup(self):
        """Create a mock pickup object."""
        pickup = MagicMock(spec=Pickup)
        pickup.pickup_id = "pik_test123"
        pickup.is_deleted = False
        pickup.notification_sent = False
        return pickup

    def test_generate_pickup_id_format(self):
        """Test that generated pickup IDs have correct format."""
        pickup_id = PickupService.generate_pickup_id()

        assert pickup_id.startswith("pik_")
        assert len(pickup_id) == 26  # pik_ (4) + 22 chars

    def test_generate_pickup_id_unique(self):
        """Test that generated pickup IDs are unique."""
        ids = [PickupService.generate_pickup_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    @pytest.mark.asyncio
    async def test_cancel_pickup_success(self, mock_session, mock_pickup):
        """Test cancelling a pickup successfully."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.cancel_pickup("pik_test123")

        assert result == mock_pickup
        assert mock_pickup.is_deleted is True
        assert mock_pickup.deleted_at is not None
        assert mock_pickup.cancelled_at is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_pickup_not_found(self, mock_session):
        """Test cancelling a non-existent pickup."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.cancel_pickup("pik_nonexistent")

        assert result is None
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pickup_by_id_found(self, mock_session, mock_pickup):
        """Test retrieving a pickup by ID with address loaded."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pickup
        mock_session.execute.return_value = mock_result

        service = PickupService(mock_session)
        result = await service.get_pickup_by_id("pik_test123")

        assert result == mock_pickup
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pickups_paginated(self, mock_session, mock_pickup):
        """Test paginated pickup retrieval."""
        # Mock pickups query result
        mock_pickups_result = MagicMock()
        mock_pickups_result.scalars.return_value.all.return_value = [mock_pickup]

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(
            side_effect=[mock_pickups_result, mock_count_result]
        )

        service = PickupService(mock_session)
        result = await service.get_pickups_paginated(page=1, items_per_page=10)

        assert len(result.pickups) == 1
        assert result.total_count == 1
        assert result.page == 1
        assert result.items_per_page == 10
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_get_pickups_paginated_empty(self, mock_session):
        """Test paginated pickup retrieval with no results."""
        # Mock pickups query result
        mock_pickups_result = MagicMock()
        mock_pickups_result.scalars.return_value.all.return_value = []

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(
            side_effect=[mock_pickups_result, mock_count_result]
        )

        service = PickupService(mock_session)
        result = await service.get_pickups_paginated(page=1, items_per_page=10)

        assert len(result.pickups) == 0
        assert result.total_count == 0
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_get_pickups_paginated_has_more(self, mock_session, mock_pickup):
        """Test paginated pickup retrieval with more pages."""
        # Mock pickups query result
        mock_pickups_result = MagicMock()
        mock_pickups_result.scalars.return_value.all.return_value = [mock_pickup] * 10

        # Mock count query result - more than one page
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_session.execute = AsyncMock(
            side_effect=[mock_pickups_result, mock_count_result]
        )

        service = PickupService(mock_session)
        result = await service.get_pickups_paginated(page=1, items_per_page=10)

        assert len(result.pickups) == 10
        assert result.total_count == 25
        assert result.has_more is True
