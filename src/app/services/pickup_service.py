"""Pickup service - Business logic for pickup operations."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..core.utils.datetime import parse_iso_datetime
from ..models.pickup import Pickup
from ..models.pickup_address import PickupAddress
from ..schemas.pickup import PickupCreate
from .base import BaseService

# Pickup ID format: pik_<RANDOM_SUFFIX>
PICKUP_ID_PREFIX = "pik_"
PICKUP_ID_SUFFIX_LENGTH = 22


class PickupValidationResult(NamedTuple):
    """Result of pickup validation for notification."""

    is_valid: bool
    pickup: Pickup | None
    skip_reason: str | None


@dataclass
class PaginatedPickups:
    """Paginated list of pickups."""

    pickups: list[Pickup]
    total_count: int
    page: int
    items_per_page: int

    @property
    def has_more(self) -> bool:
        """Check if there are more pages."""
        offset = (self.page - 1) * self.items_per_page
        return offset + len(self.pickups) < self.total_count


class PickupService(BaseService):
    """
    Service for pickup-related business logic.

    Handles pickup lifecycle operations including CRUD,
    validation, status checks, and state transitions.
    """

    @staticmethod
    def generate_pickup_id() -> str:
        """Generate a unique pickup ID in the format pik_XXXXXXXXX."""
        random_suffix = secrets.token_urlsafe(16)[:PICKUP_ID_SUFFIX_LENGTH]
        return f"{PICKUP_ID_PREFIX}{random_suffix}"

    async def create_pickup(
        self,
        pickup_data: PickupCreate,
        pickup_id: str | None = None,
        notification_job_id: str | None = None,
    ) -> Pickup:
        """
        Create a new pickup with its address.

        Args:
            pickup_data: The pickup creation data.
            pickup_id: Optional pre-generated pickup ID. If not provided, one will be generated.
            notification_job_id: Optional job ID for scheduled notification.

        Returns:
            The created Pickup model with address loaded.
        """
        # Create the pickup address
        address = PickupAddress(**pickup_data.pickup_address.model_dump())
        self.db.add(address)
        await self.db.flush()

        # Use provided pickup ID or generate one
        if pickup_id is None:
            pickup_id = self.generate_pickup_id()

        # Create the pickup record
        pickup = Pickup(
            pickup_id=pickup_id,
            label_ids=pickup_data.label_ids,
            contact_details=pickup_data.contact_details.model_dump(mode="json"),
            pickup_notes=pickup_data.pickup_notes,
            pickup_window=pickup_data.pickup_window.model_dump(mode="json"),
            pickup_address_id=address.id,
            notification_job_id=notification_job_id,
            notification_sent=False,
        )
        self.db.add(pickup)
        await self.db.commit()
        await self.db.refresh(pickup, attribute_names=["pickup_address"])

        self.logger.info("Created pickup %s", pickup_id)
        return pickup

    async def get_pickup_by_id(self, pickup_id: str) -> Pickup | None:
        """
        Retrieve a pickup by ID with address loaded.

        Args:
            pickup_id: The unique pickup identifier.

        Returns:
            The Pickup model if found and active, None otherwise.
        """
        query = (
            select(Pickup)
            .options(selectinload(Pickup.pickup_address))
            .where(Pickup.pickup_id == pickup_id, Pickup.is_deleted.is_(False))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_active_pickup(self, pickup_id: str) -> Pickup | None:
        """
        Retrieve an active (non-deleted) pickup by ID without eager loading.

        Args:
            pickup_id: The unique pickup identifier.

        Returns:
            The Pickup model if found and active, None otherwise.
        """
        query = select(Pickup).where(
            Pickup.pickup_id == pickup_id,
            Pickup.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_pickups_paginated(
        self,
        page: int = 1,
        items_per_page: int = 10,
    ) -> PaginatedPickups:
        """
        Get paginated list of active pickups.

        Args:
            page: Page number (1-indexed).
            items_per_page: Number of items per page.

        Returns:
            PaginatedPickups with pickups and pagination metadata.
        """
        offset = (page - 1) * items_per_page

        # Get pickups with address eager loaded
        query = (
            select(Pickup)
            .options(selectinload(Pickup.pickup_address))
            .where(Pickup.is_deleted.is_(False))
            .order_by(Pickup.created_at.desc())
            .offset(offset)
            .limit(items_per_page)
        )
        result = await self.db.execute(query)
        pickups = list(result.scalars().all())

        # Get total count
        count_query = (
            select(func.count()).select_from(Pickup).where(Pickup.is_deleted.is_(False))
        )
        total_count = (await self.db.execute(count_query)).scalar() or 0

        return PaginatedPickups(
            pickups=pickups,
            total_count=total_count,
            page=page,
            items_per_page=items_per_page,
        )

    async def cancel_pickup(self, pickup_id: str) -> Pickup | None:
        """
        Soft delete (cancel) a pickup.

        Args:
            pickup_id: The unique pickup identifier.

        Returns:
            The cancelled Pickup if found, None otherwise.
        """
        pickup = await self.get_active_pickup(pickup_id)
        if pickup is None:
            return None

        # Soft delete
        pickup.is_deleted = True
        pickup.deleted_at = datetime.now(UTC)
        pickup.cancelled_at = pickup.deleted_at
        await self.db.commit()

        self.logger.info("Cancelled pickup %s", pickup_id)
        return pickup

    async def validate_for_notification(self, pickup_id: str) -> PickupValidationResult:
        """
        Validate whether a pickup is eligible for notification.

        Checks:
        - Pickup exists
        - Pickup is not deleted/cancelled
        - Notification hasn't already been sent
        - Pickup window hasn't passed

        Args:
            pickup_id: The unique pickup identifier.

        Returns:
            PickupValidationResult with validation status and details.
        """
        pickup = await self.get_active_pickup(pickup_id)

        if pickup is None:
            self.logger.info(
                "Pickup %s not found or was cancelled",
                pickup_id,
            )
            return PickupValidationResult(
                is_valid=False,
                pickup=None,
                skip_reason="pickup_not_found_or_cancelled",
            )

        if pickup.notification_sent:
            self.logger.info(
                "Notification already sent for pickup %s",
                pickup_id,
            )
            return PickupValidationResult(
                is_valid=False,
                pickup=pickup,
                skip_reason="notification_already_sent",
            )

        # Check if pickup window has already passed
        pickup_window = pickup.pickup_window or {}
        start_at_raw = pickup_window.get("start_at")
        start_at = parse_iso_datetime(start_at_raw)

        if start_at is None and start_at_raw is not None:
            self.logger.warning(
                "Invalid pickup window format for pickup %s: %s",
                pickup_id,
                start_at_raw,
            )
        elif start_at is not None and start_at < datetime.now(UTC):
            self.logger.info(
                "Pickup window already passed for pickup %s",
                pickup_id,
            )
            return PickupValidationResult(
                is_valid=False,
                pickup=pickup,
                skip_reason="pickup_window_passed",
            )

        return PickupValidationResult(
            is_valid=True,
            pickup=pickup,
            skip_reason=None,
        )

    async def mark_notification_sent(self, pickup: Pickup) -> None:
        """
        Mark a pickup's notification as sent.

        Args:
            pickup: The Pickup model to update.
        """
        pickup.notification_sent = True
        await self.db.commit()
        self.logger.info(
            "Marked notification as sent for pickup %s",
            pickup.pickup_id,
        )
