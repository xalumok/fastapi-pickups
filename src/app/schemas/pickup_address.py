from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PickupAddressBase(BaseModel):
    name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=50)
    email: EmailStr | None = None
    company_name: str | None = Field(None, max_length=100)
    address_line1: str = Field(..., max_length=200)
    address_line2: str | None = Field(None, max_length=200)
    address_line3: str | None = Field(None, max_length=200)
    city_locality: str = Field(..., max_length=100)
    state_province: str = Field(..., max_length=100)
    postal_code: str = Field(..., max_length=20)
    country_code: str = Field(..., max_length=2)
    address_residential_indicator: str | None = Field("no", max_length=10)


class PickupAddressRead(PickupAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None


class PickupAddressCreate(PickupAddressBase):
    pass


class PickupAddressCreateInternal(PickupAddressBase):
    pass
