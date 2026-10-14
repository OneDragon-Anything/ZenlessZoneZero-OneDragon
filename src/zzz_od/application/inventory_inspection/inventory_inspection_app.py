"""Native application export; importing never constructs a controller."""

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.inventory_inspection.inventory_inspection import (
    inventory_application_type,
)

InventoryInspectionApplication = inventory_application_type(Application, operation_node)
