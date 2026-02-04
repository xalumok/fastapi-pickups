from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .pickup_address import PickupAddressCreate, PickupAddressRead


class ContactDetails(BaseModel):
    name: str
    email: EmailStr
    phone: str


class PickupWindow(BaseModel):
    start_at: datetime
    end_at: datetime


class PickupBase(BaseModel):
    label_ids: list[str] = Field(..., min_length=1)
    contact_details: ContactDetails
    pickup_notes: str | None = None
    pickup_window: PickupWindow


class PickupCreate(PickupBase):
    pickup_address: PickupAddressCreate


class PickupCreateInternal(BaseModel):
    pickup_id: str
    label_ids: list[str]
    contact_details: dict
    pickup_notes: str | None = None
    pickup_window: dict
    pickup_address_id: int
    carrier_id: str | None = None
    confirmation_number: str | None = None
    warehouse_id: str | None = None
    notification_job_id: str | None = None
    notification_sent: bool = False


class PickupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pickup_id: str
    label_ids: list[str]
    created_at: datetime
    cancelled_at: datetime | None = None
    carrier_id: str | None = None
    confirmation_number: str | None = None
    warehouse_id: str | None = None
    pickup_address: PickupAddressRead
    contact_details: ContactDetails
    pickup_notes: str | None = None
    pickup_window: PickupWindow


class PickupUpdate(BaseModel):
    label_ids: list[str] | None = None
    contact_details: ContactDetails | None = None
    pickup_notes: str | None = None
    pickup_window: PickupWindow | None = None


class PickupUpdateInternal(BaseModel):
    label_ids: list[str] | None = None
    contact_details: dict | None = None
    pickup_notes: str | None = None
    pickup_window: dict | None = None
    updated_at: datetime | None = None


class PickupDelete(BaseModel):
    is_deleted: bool
    deleted_at: datetime
    cancelled_at: datetime
