from fastcrud import FastCRUD

from ..models.pickup import Pickup
from ..schemas.pickup import PickupCreateInternal, PickupDelete, PickupRead, PickupUpdate, PickupUpdateInternal

CRUDPickup = FastCRUD[Pickup, PickupCreateInternal, PickupUpdate, PickupUpdateInternal, PickupDelete, PickupRead]
crud_pickups = CRUDPickup(Pickup)
