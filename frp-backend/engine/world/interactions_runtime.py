"""Interaction classification and execution runtime."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from engine.world.skill_checks import SkillCheckResult, roll_check

from .interactions_types import InteractionResult, InteractionRule, InteractionType


def classify_targets(tile: Dict[str, Any], entities: List[Dict[str, Any]]) -> List[str]:
    """Return target-type strings present at the given tile."""
    targets: List[str] = []

    for entity in entities:
        entity_type = entity.get("entity_type", "")
        disposition = entity.get("disposition", "neutral")
        alive = entity.get("alive", True)
        locked = entity.get("locked", False)
        trapped = entity.get("trapped", False)

        if entity_type == "npc" and alive:
            targets.append("npc_friendly" if disposition in ("friendly", "neutral") else "npc_hostile")
        elif entity_type == "door":
            targets.append("door_locked" if locked else "door_unlocked")
        elif entity_type == "chest":
            if trapped:
                targets.append("chest_trapped")
            elif locked:
                targets.append("chest_locked")
            else:
                targets.append("chest")
        elif entity_type == "corpse" or (entity_type == "npc" and not alive):
            targets.append("corpse")
        elif entity_type in {"workstation", "lever", "altar", "trap", "item", "bed", "barrel", "bookshelf", "shrine", "campfire", "well"}:
            targets.append(entity_type)
        elif entity_type in {"sign", "book"}:
            targets.append("sign")

    terrain = tile.get("terrain", "")
    flags = tile.get("flags", set())

    if terrain in ("deep_water", "shallow_water") or "WATER" in flags:
        targets.append("water")
    if terrain == "tree" or "TREE" in flags:
        targets.append("tree")
    if terrain == "ore_vein" or "ORE" in flags:
        targets.append("ore_vein")
    if terrain in ("stone_wall", "wood_wall", "brick_wall", "cave_wall"):
        targets.append("wall")
    if terrain == "boulder" or "BOULDER" in flags:
        targets.append("boulder")
    if terrain == "bridge" or "BRIDGE" in flags:
        targets.append("bridge")
    if terrain == "narrow_gap" or "NARROW" in flags:
        targets.append("narrow_gap")
    if tile.get("items") and "item" not in targets:
        targets.append("item")
    return targets


def available_interactions(
    tile: Dict[str, Any],
    entities_at_tile: List[Dict[str, Any]],
    _player: Dict[str, Any],
    rules: Dict[Tuple[str, InteractionType], InteractionRule],
) -> List[InteractionType]:
    seen: set[InteractionType] = set()
    result: List[InteractionType] = []
    for target_type in classify_targets(tile, entities_at_tile):
        for (rule_target, interaction_type), _rule in rules.items():
            if rule_target == target_type and interaction_type not in seen:
                seen.add(interaction_type)
                result.append(interaction_type)
    return result


class InteractionHandler:
    """Resolve an interaction into a concrete result with optional skill check."""

    def __init__(self, rules: Dict[Tuple[str, InteractionType], InteractionRule]):
        self._rules = rules

    def handle(
        self,
        interaction_type: InteractionType,
        player: Dict[str, Any],
        target: Dict[str, Any],
        context: Dict[str, Any],
    ) -> InteractionResult:
        target_type = target.get("target_type", "item")
        rule = self._rules.get((target_type, interaction_type))
        if rule is None:
            return InteractionResult(
                success=False,
                narrative_prompt=f"Cannot {interaction_type.name.lower()} this target.",
                ap_cost=0,
            )

        ap_cost = rule["ap_cost"]
        skill = rule["skill"]
        dc_lo, dc_hi = rule["dc_range"]
        dc = context.get("dc", (dc_lo + dc_hi) // 2 if dc_hi > 0 else 0)
        rng = context.get("rng")
        state_changes: Dict[str, Any] = {}
        check_result: Optional[SkillCheckResult] = None

        if skill is not None and dc > 0:
            ability_score = player.get("abilities", {}).get(skill, 10)
            check_result = roll_check(ability_score, dc, _rng=rng)
            success = check_result.success
        else:
            success = True

        action_name = interaction_type.name.lower().replace("_", " ")
        target_name = target.get("name", target_type)
        if success:
            narrative = f"The player successfully performs {action_name} on {target_name}."
            if interaction_type == InteractionType.OPEN:
                state_changes["opened"] = True
            elif interaction_type == InteractionType.LOCK_PICK:
                state_changes["locked"] = False
            elif interaction_type == InteractionType.FORCE_OPEN:
                state_changes["locked"] = False
                state_changes["broken"] = True
            elif interaction_type == InteractionType.DISARM_TRAP:
                state_changes["trapped"] = False
            elif interaction_type == InteractionType.PICK_UP:
                state_changes["picked_up"] = True
            elif interaction_type == InteractionType.REST:
                state_changes["rested"] = True
            elif interaction_type == InteractionType.CHOP:
                state_changes["chopped"] = True
            elif interaction_type == InteractionType.MINE:
                state_changes["mined"] = True
            elif interaction_type == InteractionType.CLOSE:
                state_changes["opened"] = False
        else:
            narrative = f"The player fails to {action_name} on {target_name}."
            if check_result and check_result.critical == "failure":
                narrative += " A critical failure — something goes wrong!"

        return InteractionResult(
            success=success,
            narrative_prompt=narrative,
            skill_check=check_result,
            ap_cost=ap_cost,
            state_changes=state_changes,
        )
