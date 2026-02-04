"""Scheduling service - Business logic for job scheduling via ARQ."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from ..core.config import settings


class SchedulingStatus(str, Enum):
    """Status of scheduling operation."""

    SCHEDULED = "scheduled"
    SKIPPED_PAST = "skipped_past"
    FAILED = "failed"


@dataclass
class SchedulingResult:
    """Result of a scheduling attempt."""

    status: SchedulingStatus
    job_id: str | None
    message: str


class SchedulingService:
    """
    Service for scheduling background jobs via ARQ.

    Encapsulates all ARQ/Redis interaction, making it easy to:
    - Test with mocks
    - Swap queue implementations
    - Add retry logic and error handling

    Uses lazy initialization for the Redis connection pool to reuse
    connections across multiple operations.
    """

    def __init__(
        self,
        redis_host: str | None = None,
        redis_port: int | None = None,
    ) -> None:
        """
        Initialize the scheduling service.

        Args:
            redis_host: Redis host. Defaults to settings.REDIS_QUEUE_HOST.
            redis_port: Redis port. Defaults to settings.REDIS_QUEUE_PORT.
        """
        self._redis_host = redis_host or settings.REDIS_QUEUE_HOST
        self._redis_port = redis_port or settings.REDIS_QUEUE_PORT
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pool: ArqRedis | None = None

    def _get_redis_settings(self) -> RedisSettings:
        """Get Redis connection settings."""
        return RedisSettings(host=self._redis_host, port=self._redis_port)

    async def _get_pool(self) -> ArqRedis:
        """
        Get or create the Redis connection pool.

        Uses lazy initialization to create the pool on first use
        and reuse it for subsequent operations.
        """
        if self._pool is None:
            self._pool = await create_pool(self._get_redis_settings())
        return self._pool

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    async def schedule_pickup_notification(
        self,
        pickup_id: str,
        pickup_window_start: datetime,
        notify_before: timedelta = timedelta(hours=1),
    ) -> SchedulingResult:
        """
        Schedule a pickup notification to be sent before the pickup window starts.

        Args:
            pickup_id: The unique pickup identifier.
            pickup_window_start: When the pickup window starts.
            notify_before: How long before the window to send notification.
                          Defaults to 1 hour.

        Returns:
            SchedulingResult with job ID if scheduled, or skip/error reason.
        """
        notification_time = pickup_window_start - notify_before
        now = datetime.now(UTC)

        # Don't schedule notifications in the past
        if notification_time <= now:
            self._logger.warning(
                "Notification time %s is in the past for pickup %s",
                notification_time,
                pickup_id,
            )
            return SchedulingResult(
                status=SchedulingStatus.SKIPPED_PAST,
                job_id=None,
                message="Notification time is in the past",
            )

        delay_seconds = int((notification_time - now).total_seconds())

        try:
            pool = await self._get_pool()
            job = await pool.enqueue_job(
                "send_pickup_notification",
                pickup_id,
                _defer_by=delay_seconds,
            )
            self._logger.info(
                "Scheduled notification for pickup %s at %s (job_id: %s, delay: %ds)",
                pickup_id,
                notification_time,
                job.job_id,
                delay_seconds,
            )
            return SchedulingResult(
                status=SchedulingStatus.SCHEDULED,
                job_id=job.job_id,
                message=f"Notification scheduled for {notification_time}",
            )

        except Exception as e:
            self._logger.exception(
                "Failed to schedule notification for pickup %s",
                pickup_id,
            )
            return SchedulingResult(
                status=SchedulingStatus.FAILED,
                job_id=None,
                message=f"Scheduling failed: {e}",
            )
