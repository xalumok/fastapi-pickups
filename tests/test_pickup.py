"""Unit tests for pickup API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.api.v1.pickups import (
    delete_pickup,
    get_pickup,
    get_pickups,
    schedule_pickup,
)
from src.app.core.exceptions.http_exceptions import NotFoundException
from src.app.models.pickup import Pickup
from src.app.models.pickup_address import PickupAddress
from src.app.schemas.pickup import PickupCreate
from src.app.services.pickup_service import PaginatedPickups, PickupService
from src.app.services.scheduling_service import SchedulingResult, SchedulingStatus


@pytest.fixture
def sample_pickup_address_data():
    """Generate sample pickup address data for tests."""
    return {
        "name": "John Doe",
        "phone": "+1 204-253-9411",
        "email": "john@example.com",
        "company_name": "The Home Depot",
        "address_line1": "1999 Bishop Grandin Blvd.",
        "address_line2": "Unit 408",
        "city_locality": "Winnipeg",
        "state_province": "Manitoba",
        "postal_code": "78756",
        "country_code": "CA",
        "address_residential_indicator": "no",
    }


@pytest.fixture
def sample_pickup_data(sample_pickup_address_data):
    """Generate sample pickup data for tests."""
    start_time = datetime.now(UTC) + timedelta(hours=2)
    end_time = start_time + timedelta(hours=2)

    return {
        "label_ids": ["se-28529731"],
        "contact_details": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1 204-253-9411",
        },
        "pickup_notes": "Please ring doorbell",
        "pickup_window": {
            "start_at": start_time,
            "end_at": end_time,
        },
        "pickup_address": sample_pickup_address_data,
    }


@pytest.fixture
def sample_pickup_address_orm():
    """Generate a sample PickupAddress ORM-like object."""
    address = MagicMock(spec=PickupAddress)
    address.id = 1
    address.name = "John Doe"
    address.phone = "+1 204-253-9411"
    address.email = "john@example.com"
    address.company_name = "The Home Depot"
    address.address_line1 = "1999 Bishop Grandin Blvd."
    address.address_line2 = "Unit 408"
    address.address_line3 = None
    address.city_locality = "Winnipeg"
    address.state_province = "Manitoba"
    address.postal_code = "78756"
    address.country_code = "CA"
    address.address_residential_indicator = "no"
    address.created_at = datetime.now(UTC)
    address.updated_at = None
    return address


@pytest.fixture
def sample_pickup_orm(sample_pickup_address_orm):
    """Generate a sample Pickup ORM-like object."""
    start_time = datetime.now(UTC) + timedelta(hours=2)
    end_time = start_time + timedelta(hours=2)

    pickup = MagicMock(spec=Pickup)
    pickup.pickup_id = "pik_test123456"
    pickup.label_ids = ["se-28529731"]
    pickup.created_at = datetime.now(UTC)
    pickup.cancelled_at = None
    pickup.carrier_id = None
    pickup.confirmation_number = None
    pickup.warehouse_id = None
    pickup.pickup_address_id = 1
    pickup.pickup_address = sample_pickup_address_orm
    pickup.contact_details = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1 204-253-9411",
    }
    pickup.pickup_notes = "Please ring doorbell"
    pickup.pickup_window = {
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    }
    pickup.notification_job_id = "job_123"
    pickup.notification_sent = False
    pickup.is_deleted = False
    pickup.deleted_at = None
    return pickup


@pytest.fixture
def mock_pickup_service(sample_pickup_orm):
    """Create a mock pickup service."""
    service = MagicMock(spec=PickupService)
    service.create_pickup = AsyncMock(return_value=sample_pickup_orm)
    service.get_pickup_by_id = AsyncMock(return_value=sample_pickup_orm)
    service.get_active_pickup = AsyncMock(return_value=sample_pickup_orm)
    service.get_pickups_paginated = AsyncMock(
        return_value=PaginatedPickups(
            pickups=[sample_pickup_orm],
            total_count=1,
            page=1,
            items_per_page=10,
        )
    )
    service.cancel_pickup = AsyncMock(return_value=sample_pickup_orm)
    return service


@pytest.fixture
def mock_scheduling_service():
    """Create a mock scheduling service."""
    service = MagicMock()
    service.schedule_pickup_notification = AsyncMock(
        return_value=SchedulingResult(
            status=SchedulingStatus.SCHEDULED,
            job_id="job_123",
            message="Scheduled",
        )
    )
    return service


class TestSchedulePickup:
    """Test pickup scheduling endpoint."""

    @pytest.mark.asyncio
    async def test_schedule_pickup_success(
        self,
        sample_pickup_data,
        mock_pickup_service,
        mock_scheduling_service,
    ):
        """Test successful pickup creation."""
        pickup_create = PickupCreate(**sample_pickup_data)

        result = await schedule_pickup(
            pickup_create, mock_pickup_service, mock_scheduling_service
        )

        assert result.pickup_id == "pik_test123456"
        mock_scheduling_service.schedule_pickup_notification.assert_called_once()
        mock_pickup_service.create_pickup.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_pickup_creation_fails(
        self, sample_pickup_data, mock_pickup_service, mock_scheduling_service
    ):
        """Test pickup creation when service fails."""
        pickup_create = PickupCreate(**sample_pickup_data)

        # Mock service to raise exception
        mock_pickup_service.create_pickup = AsyncMock(
            side_effect=Exception("Database error")
        )

        with pytest.raises(Exception, match="Database error"):
            await schedule_pickup(
                pickup_create, mock_pickup_service, mock_scheduling_service
            )


class TestGetPickup:
    """Test get pickup endpoint."""

    @pytest.mark.asyncio
    async def test_get_pickup_success(self, mock_pickup_service, sample_pickup_orm):
        """Test successful pickup retrieval."""
        pickup_id = "pik_test123456"

        result = await get_pickup(pickup_id, mock_pickup_service)

        assert result.pickup_id == pickup_id
        mock_pickup_service.get_pickup_by_id.assert_called_once_with(pickup_id)

    @pytest.mark.asyncio
    async def test_get_pickup_not_found(self, mock_pickup_service):
        """Test pickup retrieval when pickup doesn't exist."""
        pickup_id = "pik_nonexistent"

        # Mock service to return None
        mock_pickup_service.get_pickup_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException, match="Pickup not found"):
            await get_pickup(pickup_id, mock_pickup_service)


class TestDeletePickup:
    """Test delete pickup endpoint."""

    @pytest.mark.asyncio
    async def test_delete_pickup_success(
        self, mock_pickup_service, sample_pickup_orm, mock_scheduling_service
    ):
        """Test successful pickup deletion."""
        pickup_id = "pik_test123456"

        result = await delete_pickup(
            pickup_id, mock_pickup_service, mock_scheduling_service
        )

        assert result == {"message": "Pickup cancelled successfully"}
        mock_pickup_service.get_active_pickup.assert_called_once_with(pickup_id)
        mock_pickup_service.cancel_pickup.assert_called_once_with(pickup_id)

    @pytest.mark.asyncio
    async def test_delete_pickup_not_found(
        self, mock_pickup_service, mock_scheduling_service
    ):
        """Test pickup deletion when pickup doesn't exist."""
        pickup_id = "pik_nonexistent"

        # Mock service to return None
        mock_pickup_service.get_active_pickup = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException, match="Pickup not found"):
            await delete_pickup(pickup_id, mock_pickup_service, mock_scheduling_service)

    @pytest.mark.asyncio
    async def test_delete_pickup_without_notification(
        self, mock_pickup_service, sample_pickup_orm, mock_scheduling_service
    ):
        """Test pickup deletion when no notification was scheduled."""
        pickup_id = "pik_test123456"

        # Set notification_job_id to None
        sample_pickup_orm.notification_job_id = None
        mock_pickup_service.get_active_pickup = AsyncMock(
            return_value=sample_pickup_orm
        )

        result = await delete_pickup(
            pickup_id, mock_pickup_service, mock_scheduling_service
        )

        assert result == {"message": "Pickup cancelled successfully"}
        mock_pickup_service.cancel_pickup.assert_called_once_with(pickup_id)


class TestGetPickups:
    """Test get all pickups endpoint."""

    @pytest.mark.asyncio
    async def test_get_pickups_success(self, mock_pickup_service, sample_pickup_orm):
        """Test successful pickups list retrieval."""
        result = await get_pickups(
            pickup_service=mock_pickup_service, page=1, items_per_page=10
        )

        assert "data" in result
        assert "total_count" in result
        assert "page" in result
        assert "items_per_page" in result
        assert result["page"] == 1
        assert result["items_per_page"] == 10
        assert result["total_count"] == 1
        assert len(result["data"]) == 1
        mock_pickup_service.get_pickups_paginated.assert_called_once_with(
            page=1, items_per_page=10
        )

    @pytest.mark.asyncio
    async def test_get_pickups_empty(self, mock_pickup_service):
        """Test pickups list retrieval when no pickups exist."""
        # Mock service to return empty result
        mock_pickup_service.get_pickups_paginated = AsyncMock(
            return_value=PaginatedPickups(
                pickups=[],
                total_count=0,
                page=1,
                items_per_page=10,
            )
        )

        result = await get_pickups(
            pickup_service=mock_pickup_service, page=1, items_per_page=10
        )

        assert result["data"] == []
        assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_get_pickups_pagination(self, mock_pickup_service, sample_pickup_orm):
        """Test pickups list with pagination parameters."""
        # Mock service to return paginated result
        mock_pickup_service.get_pickups_paginated = AsyncMock(
            return_value=PaginatedPickups(
                pickups=[sample_pickup_orm] * 5,
                total_count=25,
                page=2,
                items_per_page=5,
            )
        )

        result = await get_pickups(
            pickup_service=mock_pickup_service, page=2, items_per_page=5
        )

        assert len(result["data"]) == 5
        assert result["total_count"] == 25
        assert result["page"] == 2
        assert result["items_per_page"] == 5
        assert result["has_more"] is True  # 5 + 5 < 25
