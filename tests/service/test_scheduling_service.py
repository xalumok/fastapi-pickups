"""Unit tests for SchedulingService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.services.scheduling_service import (
    SchedulingResult,
    SchedulingService,
    SchedulingStatus,
)


class TestSchedulingService:
    """Test SchedulingService job scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_notification_in_past(self):
        """Test scheduling notification for past time is skipped."""
        service = SchedulingService()
        past_time = datetime.now(UTC) - timedelta(hours=2)

        result = await service.schedule_pickup_notification(
            pickup_id="pik_test123",
            pickup_window_start=past_time,
        )

        assert result.status == SchedulingStatus.SKIPPED_PAST
        assert result.job_id is None
        assert "past" in result.message.lower()

    @pytest.mark.asyncio
    async def test_schedule_notification_exactly_now(self):
        """Test scheduling notification for exactly now is skipped."""
        service = SchedulingService()
        # notify_before defaults to 1 hour, so window start needs to be > 1 hour from now
        now_time = datetime.now(UTC) + timedelta(minutes=30)  # Less than 1 hour

        result = await service.schedule_pickup_notification(
            pickup_id="pik_test123",
            pickup_window_start=now_time,
        )

        assert result.status == SchedulingStatus.SKIPPED_PAST
        assert result.job_id is None

    @pytest.mark.asyncio
    async def test_schedule_notification_success(self):
        """Test successful notification scheduling."""
        # Create mock job
        mock_job = MagicMock()
        mock_job.job_id = "job_123"

        # Create mock pool
        mock_pool = MagicMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.aclose = AsyncMock()

        service = SchedulingService()

        # Patch the pool creation
        with patch.object(service, "_get_pool", return_value=mock_pool):
            future_time = datetime.now(UTC) + timedelta(hours=3)
            result = await service.schedule_pickup_notification(
                pickup_id="pik_test123",
                pickup_window_start=future_time,
            )

        assert result.status == SchedulingStatus.SCHEDULED
        assert result.job_id == "job_123"
        mock_pool.enqueue_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_notification_custom_notify_before(self):
        """Test scheduling with custom notify_before time."""
        mock_job = MagicMock()
        mock_job.job_id = "job_456"

        mock_pool = MagicMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

        service = SchedulingService()

        with patch.object(service, "_get_pool", return_value=mock_pool):
            future_time = datetime.now(UTC) + timedelta(hours=5)
            result = await service.schedule_pickup_notification(
                pickup_id="pik_test123",
                pickup_window_start=future_time,
                notify_before=timedelta(hours=2),
            )

        assert result.status == SchedulingStatus.SCHEDULED
        assert result.job_id == "job_456"

    @pytest.mark.asyncio
    async def test_schedule_notification_failure(self):
        """Test notification scheduling failure."""
        service = SchedulingService()

        # Patch to raise exception
        async def mock_get_pool():
            raise Exception("Redis connection failed")

        with patch.object(service, "_get_pool", mock_get_pool):
            future_time = datetime.now(UTC) + timedelta(hours=3)
            result = await service.schedule_pickup_notification(
                pickup_id="pik_test123",
                pickup_window_start=future_time,
            )

        assert result.status == SchedulingStatus.FAILED
        assert result.job_id is None
        assert "failed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_close_pool(self):
        """Test closing the connection pool."""
        service = SchedulingService()

        # Set a mock pool
        mock_pool = MagicMock()
        mock_pool.aclose = AsyncMock()
        service._pool = mock_pool

        await service.close()

        mock_pool.aclose.assert_called_once()
        assert service._pool is None

    @pytest.mark.asyncio
    async def test_close_pool_when_none(self):
        """Test closing when pool is None doesn't error."""
        service = SchedulingService()
        service._pool = None

        # Should not raise
        await service.close()
        assert service._pool is None

    @pytest.mark.asyncio
    async def test_close_pool_multiple_times(self):
        """Test closing pool multiple times is safe."""
        service = SchedulingService()

        mock_pool = MagicMock()
        mock_pool.aclose = AsyncMock()
        service._pool = mock_pool

        await service.close()
        await service.close()  # Should not raise

        # aclose should only be called once
        mock_pool.aclose.assert_called_once()

    def test_get_redis_settings(self):
        """Test Redis settings generation."""
        service = SchedulingService(redis_host="custom-host", redis_port=6380)

        settings = service._get_redis_settings()

        assert settings.host == "custom-host"
        assert settings.port == 6380

    def test_default_redis_settings(self):
        """Test default Redis settings from config."""
        service = SchedulingService()

        # Should use settings from config
        assert service._redis_host is not None
        assert service._redis_port is not None


class TestSchedulingResult:
    """Test SchedulingResult dataclass."""

    def test_scheduling_result_scheduled(self):
        """Test creating a scheduled result."""
        result = SchedulingResult(
            status=SchedulingStatus.SCHEDULED,
            job_id="job_123",
            message="Scheduled successfully",
        )

        assert result.status == SchedulingStatus.SCHEDULED
        assert result.job_id == "job_123"
        assert result.message == "Scheduled successfully"

    def test_scheduling_result_skipped(self):
        """Test creating a skipped result."""
        result = SchedulingResult(
            status=SchedulingStatus.SKIPPED_PAST,
            job_id=None,
            message="Time is in the past",
        )

        assert result.status == SchedulingStatus.SKIPPED_PAST
        assert result.job_id is None

    def test_scheduling_result_failed(self):
        """Test creating a failed result."""
        result = SchedulingResult(
            status=SchedulingStatus.FAILED,
            job_id=None,
            message="Redis connection error",
        )

        assert result.status == SchedulingStatus.FAILED
        assert result.job_id is None


class TestSchedulingStatus:
    """Test SchedulingStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert SchedulingStatus.SCHEDULED == "scheduled"
        assert SchedulingStatus.SKIPPED_PAST == "skipped_past"
        assert SchedulingStatus.FAILED == "failed"

    def test_status_is_string(self):
        """Test status values are strings."""
        assert isinstance(SchedulingStatus.SCHEDULED.value, str)
        assert isinstance(SchedulingStatus.SKIPPED_PAST.value, str)
        assert isinstance(SchedulingStatus.FAILED.value, str)
