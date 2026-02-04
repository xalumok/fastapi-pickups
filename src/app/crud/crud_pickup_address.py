from fastcrud import FastCRUD

from ..models.pickup_address import PickupAddress
from ..schemas.pickup_address import PickupAddressCreate, PickupAddressCreateInternal, PickupAddressRead

CRUDPickupAddress = FastCRUD[
    PickupAddress,
    PickupAddressCreateInternal,
    PickupAddressCreate,
    PickupAddressCreateInternal,
    PickupAddressRead,
    PickupAddressRead
]
crud_pickup_addresses = CRUDPickupAddress(PickupAddress)
