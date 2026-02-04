"""Notification service - Business logic for sending notifications."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ..models.pickup import Pickup


class NotificationChannel(str, Enum):
    """Available notification channels."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NotificationResult:
    """Result of a notification attempt."""

    status: NotificationStatus
    channel: NotificationChannel | None
    message: str
    error: str | None = None


class NotificationProvider(Protocol):
    """Protocol for notification providers (email, SMS, etc.)."""

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> bool:
        """Send a notification. Returns True if successful."""
        ...


class BaseNotificationProvider(ABC):
    """Base class for notification providers."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> bool:
        """Send a notification. Returns True if successful."""
        ...


class LoggingNotificationProvider(BaseNotificationProvider):
    """
    Development notification provider that logs instead of sending.

    Use this for local development and testing.
    In production, replace with EmailNotificationProvider, SMSNotificationProvider, etc.
    """

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> bool:
        """Log the notification instead of sending."""
        self._logger.info(
            "NOTIFICATION [%s]: %s - %s",
            recipient,
            subject,
            body,
        )
        return True


class NotificationService:
    """
    Service for handling pickup notifications.

    Coordinates notification delivery across different channels
    and handles retry logic, logging, and error handling.
    """

    def __init__(
        self,
        provider: NotificationProvider | None = None,
    ) -> None:
        """
        Initialize the notification service.

        Args:
            provider: Notification provider implementation.
                     Defaults to LoggingNotificationProvider for development.
        """
        self._provider = provider or LoggingNotificationProvider()
        self._logger = logging.getLogger(self.__class__.__name__)

    async def send_pickup_reminder(
        self,
        pickup: Pickup,
    ) -> NotificationResult:
        """
        Send a pickup reminder notification.

        Args:
            pickup: The Pickup model with contact and scheduling details.

        Returns:
            NotificationResult with delivery status.
        """
        contact_details = pickup.contact_details or {}
        recipient_email = contact_details.get("email")
        recipient_name = contact_details.get("name", "Customer")

        if not recipient_email:
            self._logger.warning(
                "No email found for pickup %s",
                pickup.pickup_id,
            )
            return NotificationResult(
                status=NotificationStatus.SKIPPED,
                channel=None,
                message="No recipient email configured",
            )

        pickup_window = pickup.pickup_window or {}
        start_at = pickup_window.get("start_at", "scheduled time")

        subject = f"Pickup Reminder: {pickup.pickup_id}"
        body = (
            f"Hello {recipient_name},\n\n"
            f"This is a reminder that your pickup ({pickup.pickup_id}) "
            f"is scheduled to start at {start_at}.\n\n"
            f"Please ensure your packages are ready for collection.\n\n"
            f"Thank you!"
        )

        try:
            success = await self._provider.send(
                recipient=recipient_email,
                subject=subject,
                body=body,
            )

            if success:
                self._logger.info(
                    "Notification sent for pickup %s to %s",
                    pickup.pickup_id,
                    recipient_email,
                )
                return NotificationResult(
                    status=NotificationStatus.SENT,
                    channel=NotificationChannel.EMAIL,
                    message=f"Notification sent to {recipient_email}",
                )
            else:
                return NotificationResult(
                    status=NotificationStatus.FAILED,
                    channel=NotificationChannel.EMAIL,
                    message="Provider returned failure",
                    error="send() returned False",
                )

        except Exception as e:
            self._logger.exception(
                "Failed to send notification for pickup %s",
                pickup.pickup_id,
            )
            return NotificationResult(
                status=NotificationStatus.FAILED,
                channel=NotificationChannel.EMAIL,
                message="Exception during send",
                error=str(e),
            )
