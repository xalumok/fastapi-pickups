"""
Background worker functions for ARQ task queue.

These functions are thin orchestrators that delegate to service classes
for business logic. This keeps worker functions simple and testable.
"""

import asyncio
import logging
from typing import Any

import structlog
import uvloop
from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import async_engine
from ...services.notification_service import NotificationService, NotificationStatus
from ...services.pickup_service import PickupService

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger(__name__)


# -------- background tasks --------
async def sample_background_task(ctx: Worker, name: str) -> str:
    """Sample background task for testing worker functionality."""
    await asyncio.sleep(5)
    return f"Task {name} is complete!"


async def send_pickup_notification(ctx: Worker, pickup_id: str) -> str:
    """
    Send notification about upcoming pickup.

    This is a thin orchestrator that:
    1. Creates a database session
    2. Validates the pickup via PickupService
    3. Sends notification via NotificationService
    4. Updates pickup state

    Args:
        ctx: ARQ worker context.
        pickup_id: The unique pickup identifier.

    Returns:
        Status message describing the outcome.
    """
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        # Initialize services
        pickup_service = PickupService(session)
        notification_service = NotificationService()

        # Validate pickup is eligible for notification
        validation = await pickup_service.validate_for_notification(pickup_id)

        if not validation.is_valid:
            logger.info(
                "Skipping notification for pickup %s: %s",
                pickup_id,
                validation.skip_reason,
            )
            return (
                f"Notification skipped for pickup {pickup_id}: {validation.skip_reason}"
            )

        # Send the notification
        pickup = validation.pickup
        result = await notification_service.send_pickup_reminder(pickup)

        if result.status == NotificationStatus.SENT:
            # Mark notification as sent in database
            await pickup_service.mark_notification_sent(pickup)
            return f"Notification sent for pickup {pickup_id}"

        elif result.status == NotificationStatus.SKIPPED:
            logger.warning(
                "Notification skipped for pickup %s: %s",
                pickup_id,
                result.message,
            )
            return f"Notification skipped for pickup {pickup_id}: {result.message}"

        else:
            logger.error(
                "Notification failed for pickup %s: %s",
                pickup_id,
                result.error or result.message,
            )
            return f"Notification failed for pickup {pickup_id}: {result.message}"


# -------- base functions --------
async def startup(ctx: Worker) -> None:
    """Called when the worker starts up."""
    logger.info("Worker started")


async def shutdown(ctx: Worker) -> None:
    """Called when the worker shuts down."""
    logger.info("Worker shutdown")


async def on_job_start(ctx: dict[str, Any]) -> None:
    """Called at the start of each job."""
    structlog.contextvars.bind_contextvars(job_id=ctx["job_id"])
    logger.info("Job started")


async def on_job_end(ctx: dict[str, Any]) -> None:
    """Called at the end of each job."""
    logger.info("Job completed")
    structlog.contextvars.clear_contextvars()
