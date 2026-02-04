from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class PickupAddress(Base):
    __tablename__ = "pickup_address"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, init=False)

    # Required fields first
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(50))
    address_line1: Mapped[str] = mapped_column(String(200))
    city_locality: Mapped[str] = mapped_column(String(100))
    state_province: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    country_code: Mapped[str] = mapped_column(String(2))

    # Optional fields with defaults
    email: Mapped[str | None] = mapped_column(String(100), default=None)
    company_name: Mapped[str | None] = mapped_column(String(100), default=None)
    address_line2: Mapped[str | None] = mapped_column(String(200), default=None)
    address_line3: Mapped[str | None] = mapped_column(String(200), default=None)
    address_residential_indicator: Mapped[str | None] = mapped_column(String(10), default="no")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
