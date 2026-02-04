"""
Pickup scheduling API endpoints.

This module provides REST API endpoints for managing pickup schedules.
Business logic is delegated to service classes.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...schemas.pickup import PickupCreate, PickupRead
from ...services.pickup_service import PickupService
from ...services.scheduling_service import SchedulingService

router = APIRouter(prefix="/pickups", tags=["pickups"])

logger = logging.getLogger(__name__)


def get_scheduling_service() -> SchedulingService:
    """Dependency for SchedulingService."""
    return SchedulingService()


async def get_pickup_service(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> PickupService:
    """Dependency for PickupService."""
    return PickupService(db)


@router.post("/", response_model=PickupRead, status_code=201)
async def schedule_pickup(
    pickup_data: PickupCreate,
    pickup_service: Annotated[PickupService, Depends(get_pickup_service)],
    scheduling: Annotated[SchedulingService, Depends(get_scheduling_service)],
) -> PickupRead:
    """
    Schedule a new pickup with address and notification.

    Creates a pickup record with the associated address and schedules
    a notification to be sent before the pickup window starts.
    """
    # Generate pickup ID upfront so we can use it for scheduling
    pickup_id = PickupService.generate_pickup_id()

    # Schedule notification
    scheduling_result = await scheduling.schedule_pickup_notification(
        pickup_id=pickup_id,
        pickup_window_start=pickup_data.pickup_window.start_at,
    )

    # Create pickup via service
    pickup = await pickup_service.create_pickup(
        pickup_data=pickup_data,
        pickup_id=pickup_id,
        notification_job_id=scheduling_result.job_id,
    )

    logger.info(
        "Created pickup %s (notification: %s)",
        pickup.pickup_id,
        scheduling_result.status.value,
    )

    return PickupRead.model_validate(pickup)


@router.get("/", response_model=dict)
async def get_pickups(
    pickup_service: Annotated[PickupService, Depends(get_pickup_service)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict[str, Any]:
    """
    Get all pickups with pagination.

    Returns a paginated list of active (non-deleted) pickups.
    """
    result = await pickup_service.get_pickups_paginated(
        page=page,
        items_per_page=items_per_page,
    )

    return {
        "data": [PickupRead.model_validate(p) for p in result.pickups],
        "total_count": result.total_count,
        "has_more": result.has_more,
        "page": result.page,
        "items_per_page": result.items_per_page,
    }


@router.get("/{pickup_id}", response_model=PickupRead)
async def get_pickup(
    pickup_id: str,
    pickup_service: Annotated[PickupService, Depends(get_pickup_service)],
) -> PickupRead:
    """
    Get a pickup by its ID.

    Returns the pickup details including address information.
    """
    pickup = await pickup_service.get_pickup_by_id(pickup_id)

    if pickup is None:
        raise NotFoundException("Pickup not found")

    return PickupRead.model_validate(pickup)


@router.delete("/{pickup_id}")
async def delete_pickup(
    pickup_id: str,
    pickup_service: Annotated[PickupService, Depends(get_pickup_service)],
    scheduling: Annotated[SchedulingService, Depends(get_scheduling_service)],
) -> dict[str, str]:
    """
    Cancel/delete a scheduled pickup.

    Performs a soft delete and attempts to cancel any scheduled notifications.
    """
    # Get pickup to check for notification job
    pickup = await pickup_service.get_active_pickup(pickup_id)

    if pickup is None:
        raise NotFoundException("Pickup not found")

    # Cancel pickup via service
    await pickup_service.cancel_pickup(pickup_id)

    return {"message": "Pickup cancelled successfully"}
