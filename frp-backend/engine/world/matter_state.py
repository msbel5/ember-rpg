"""
Matter state system for physical inventory.
Determines how items can be stored, transported, and contained.
"""
from enum import Enum
from typing import Dict, List, Optional, Tuple


class MatterState(str, Enum):
    """Physical state of an item determines what containers can hold it."""
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    ETHEREAL = "ethereal"  # magical, only bag of holding etc.


# Container acceptance rules
CONTAINER_RULES: Dict[str, Dict] = {
    # Standard solid containers
    "backpack": {"accepted_states": [MatterState.SOLID], "sealed": False},
    "belt_pouch": {"accepted_states": [MatterState.SOLID], "sealed": False},
    "pocket": {"accepted_states": [MatterState.SOLID], "sealed": False},
    "quiver": {"accepted_states": [MatterState.SOLID], "sealed": False},
    # Liquid containers
    "waterskin": {"accepted_states": [MatterState.LIQUID], "sealed": False, "liquid_capacity_ml": 500},
    "glass_bottle": {"accepted_states": [MatterState.LIQUID], "sealed": False, "liquid_capacity_ml": 750},
    "glass_vial": {"accepted_states": [MatterState.LIQUID], "sealed": False, "liquid_capacity_ml": 100},
    "barrel": {"accepted_states": [MatterState.LIQUID], "sealed": False, "liquid_capacity_ml": 5000},
    # Sealed containers (can hold gas)
    "iron_barrel": {"accepted_states": [MatterState.LIQUID, MatterState.GAS], "sealed": True, "liquid_capacity_ml": 5000},
    "rubber_balloon": {"accepted_states": [MatterState.GAS], "sealed": True, "gas_capacity_ml": 2000},
    # Magical containers
    "bag_of_holding": {"accepted_states": [MatterState.SOLID, MatterState.LIQUID, MatterState.GAS, MatterState.ETHEREAL], "sealed": True},
}


def validate_storage(
    container_type: str,
    item_matter_state: MatterState,
    container_data: Optional[Dict] = None,
) -> Tuple[bool, str]:
    """Check if an item with given matter state can be stored in the container type.

    Returns (can_store, reason_if_not).
    """
    rules = container_data or CONTAINER_RULES.get(container_type, {})
    accepted = rules.get("accepted_states", [MatterState.SOLID])

    if item_matter_state not in accepted:
        if item_matter_state == MatterState.LIQUID:
            return False, "You need a container (waterskin, bottle) to carry liquids."
        if item_matter_state == MatterState.GAS:
            if not rules.get("sealed", False):
                return False, "You need a sealed container (iron barrel, balloon) for gases."
            return False, "This container can't hold gas."
        if item_matter_state == MatterState.ETHEREAL:
            return False, "Only magical containers can hold ethereal items."
        return False, f"This container doesn't accept {item_matter_state.value} items."

    return True, ""


def get_matter_state(item_data: Dict) -> MatterState:
    """Extract matter state from item data dict, defaulting to SOLID."""
    raw = item_data.get("matter_state", "solid")
    try:
        return MatterState(raw)
    except ValueError:
        return MatterState.SOLID
