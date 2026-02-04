from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base

# Import for type hints
if TYPE_CHECKING:
    from .pickup_address import PickupAddress


class Pickup(Base):
    __tablename__ = "pickup"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, init=False)
    pickup_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # Foreign key to pickup address
    pickup_address_id: Mapped[int] = mapped_column(
        ForeignKey("pickup_address.id"), index=True
    )

    # Array of label IDs with default
    label_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default_factory=list)

    # JSONB fields with defaults
    contact_details: Mapped[dict] = mapped_column(JSONB, default_factory=dict)
    pickup_window: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    # Optional text field
    pickup_notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Optional carrier and confirmation details
    carrier_id: Mapped[str | None] = mapped_column(String(50), default=None)
    confirmation_number: Mapped[str | None] = mapped_column(String(50), default=None)
    warehouse_id: Mapped[str | None] = mapped_column(String(50), default=None)

    # Notification tracking
    notification_job_id: Mapped[str | None] = mapped_column(String(100), default=None)
    notification_sent: Mapped[bool] = mapped_column(default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)

    # Relationship
    pickup_address: Mapped["PickupAddress"] = relationship(init=False, lazy="joined")
