"""Compatibility wrapper for focused inventory mixins."""
from __future__ import annotations

from engine.api.handlers.inventory_crafting import InventoryCraftingMixin
from engine.api.handlers.inventory_equipment import InventoryEquipmentMixin
from engine.api.handlers.inventory_management import InventoryManagementMixin


class InventoryMixin(InventoryManagementMixin, InventoryEquipmentMixin, InventoryCraftingMixin):
    """Aggregate inventory mixin with listing, equipment, and crafting split by concern."""
