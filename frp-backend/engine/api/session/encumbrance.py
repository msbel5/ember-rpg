"""Encumbrance and item-addition helpers for GameSession."""
from __future__ import annotations

from typing import Any, Dict, Optional

from engine.world.inventory import ItemStack


class SessionEncumbranceMixin:
    """Carry-weight and item-addition methods."""

    def current_carry_weight(self) -> float:
        if self.physical_inventory is None:
            return 0.0
        return float(self.physical_inventory.total_carried_weight())

    def max_carry_weight(self) -> float:
        if self.physical_inventory is None:
            return 0.0
        return float(self.physical_inventory.max_carry_weight(self._get_strength_modifier()))

    def carry_ratio(self) -> float:
        max_weight = self.max_carry_weight()
        if max_weight <= 0:
            return 999.0
        return self.current_carry_weight() / max_weight

    def agi_check_penalty(self) -> int:
        penalty = 0
        ratio = self.carry_ratio()
        if 1.0 < ratio <= 1.25:
            penalty += 2
        active_back_strain = self.active_timed_conditions().get("back_strain")
        if active_back_strain is not None:
            penalty += int(active_back_strain.get("agi_check_penalty", 0))
        return penalty

    def movement_ap_penalty(self) -> int:
        penalty = 0
        active_back_strain = self.active_timed_conditions().get("back_strain")
        if active_back_strain is not None:
            penalty += int(active_back_strain.get("movement_ap_penalty", 0))
        return penalty

    def assess_item_addition(self, item: Any, merge: bool = True) -> Dict[str, Any]:
        normalized = self._normalize_item_record(item)
        stack = ItemStack.from_legacy_dict(normalized)
        projected_weight = self.current_carry_weight() + float(stack.weight)
        max_weight = self.max_carry_weight()
        projected_ratio = (projected_weight / max_weight) if max_weight > 0 else 999.0
        fits_containers = self.physical_inventory.can_add_item_auto(stack, merge=merge)
        reason = "ok"
        allowed = True
        if projected_ratio > 1.25:
            allowed = False
            reason = "overweight"
        elif not fits_containers:
            allowed = False
            reason = "no_space"
        return {
            "allowed": allowed,
            "reason": reason,
            "normalized": normalized,
            "projected_weight": projected_weight,
            "max_weight": max_weight,
            "projected_ratio": projected_ratio,
            "item_name": normalized.get("name", "item"),
        }

    def _record_add_item_failure(self, status: Dict[str, Any]) -> None:
        self.narration_context["_last_add_item_error"] = {
            "reason": status.get("reason"),
            "item_name": status.get("item_name"),
            "projected_weight": round(float(status.get("projected_weight", 0.0)), 1),
            "max_weight": round(float(status.get("max_weight", 0.0)), 1),
            "projected_ratio": round(float(status.get("projected_ratio", 0.0)), 3),
        }
        if status.get("reason") == "overweight":
            self.apply_timed_condition(
                "back_strain",
                1.0,
                movement_ap_penalty=1,
                agi_check_penalty=2,
            )

    def can_add_item(self, item: Any, merge: bool = True) -> bool:
        return bool(self.assess_item_addition(item, merge=merge)["allowed"])

    def add_item(self, item: Any, merge: bool = True) -> Optional[Dict[str, Any]]:
        status = self.assess_item_addition(item, merge=merge)
        normalized = status["normalized"]
        if not status["allowed"]:
            self._record_add_item_failure(status)
            return None
        stack = ItemStack.from_legacy_dict(normalized)
        success, _ = self.physical_inventory.add_item_auto(stack, merge=merge)
        if not success:
            self._record_add_item_failure({
                **status,
                "reason": "no_space",
                "allowed": False,
            })
            return None
        self.narration_context.pop("_last_add_item_error", None)
        self.sync_player_state()
        return normalized
