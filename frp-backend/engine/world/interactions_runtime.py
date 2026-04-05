"""Interaction classification and execution runtime."""
from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from engine.data.classes import get_skill_stat_map
from engine.world.skill_checks import SkillCheckResult, ability_modifier, roll_check

from .interactions_types import InteractionResult, InteractionRule, InteractionType

_ABILITY_IDS = {"MIG", "AGI", "END", "MND", "INS", "PRE"}
_INTERACTION_ID_OVERRIDES = {
    InteractionType.PICK_UP: "pickup",
}
_INTERACTION_ID_ALIASES = {
    "pick_up": InteractionType.PICK_UP,
    "pickup": InteractionType.PICK_UP,
}
_INTERACTION_SKILL_ALIASES = {
    "search": "perception",
    "lock_pick": "sleight_of_hand",
    "force_open": "athletics",
    "climb": "acrobatics",
    "read": "investigation",
    "pray": "INS",
    "push": "athletics",
    "pull": "athletics",
    "steal": "sleight_of_hand",
    "sneak": "stealth",
    "intimidate": "intimidation",
    "persuade": "persuasion",
    "bribe": "persuasion",
    "chop": "athletics",
    "mine": "athletics",
    "fish": "survival",
    "disarm_trap": "sleight_of_hand",
    "set_trap": "sleight_of_hand",
    "craft": "MND",
    "swim": "END",
    "flee": "AGI",
    "follow": "PRE",
    "hire": "PRE",
}
_FIXED_VERB_INTERACTION_IDS = {
    "talk",
    "attack",
    "examine",
    "use",
    "rest",
    "trade",
    "pickup",
    "open",
    "close",
    "drink",
    "fill",
    "loot",
    "bury",
}
_REQUIREMENT_ITEM_ALIASES = {
    "lockpick": {"lockpick", "lockpick_set"},
    "axe": {"axe", "hand_axe", "wood_axe"},
    "pickaxe": {"pickaxe", "mining_pick", "miner_pick"},
    "waterskin": {"waterskin"},
    "fishing_rod": {"fishing_rod", "fishing_hook"},
    "trap_kit": {"trap_kit"},
}
_GENERIC_TEMPLATE_TARGET_TYPES = {
    "altar": "altar",
    "barrel": "barrel",
    "bed": "bed",
    "bookshelf": "bookshelf",
    "bridge": "bridge",
    "campfire": "campfire",
    "corpse": "corpse",
    "crate": "crate",
    "item": "item",
    "ladder": "ladder",
    "lever": "lever",
    "ore_vein": "ore_vein",
    "shrine": "shrine",
    "sign": "sign",
    "trap": "trap",
    "tree": "tree",
    "wall": "wall",
    "water": "water",
    "well": "well",
    "window": "window",
    "workstation": "workstation",
}
_FIXTURE_TEMPLATES = {
    "bar_counter",
    "bench",
    "chair",
    "desk",
    "display_table",
    "map_table",
    "stool",
    "table",
    "trough",
}


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


def interaction_type_id(interaction_type: InteractionType) -> str:
    return _INTERACTION_ID_OVERRIDES.get(interaction_type, interaction_type.name.lower())


def parse_interaction_type(interaction_id: str | None) -> InteractionType | None:
    normalized = str(interaction_id or "").strip().lower()
    if not normalized:
        return None
    if normalized in _INTERACTION_ID_ALIASES:
        return _INTERACTION_ID_ALIASES[normalized]
    try:
        return InteractionType[normalized.upper()]
    except KeyError:
        return None


def interaction_label(interaction_type: InteractionType) -> str:
    label = interaction_type_id(interaction_type).replace("_", " ")
    compact = {
        "pickup": "Pickup",
        "lock pick": "Lockpick",
        "force open": "Force Open",
        "disarm trap": "Disarm Trap",
        "set trap": "Set Trap",
    }
    return compact.get(label, label.title())


def interaction_target_type_for_entity(entity: Dict[str, Any]) -> str | None:
    if not isinstance(entity, dict):
        return None
    explicit = str(entity.get("interaction_target_type", "")).strip().lower()
    if explicit:
        return explicit

    entity_type = str(entity.get("entity_type", entity.get("type", ""))).strip().lower()
    disposition = str(entity.get("disposition", entity.get("attitude", "neutral"))).strip().lower()
    alive = bool(entity.get("alive", True))
    locked = bool(entity.get("locked", False))
    trapped = bool(entity.get("trapped", False))
    template = str(entity.get("template", entity.get("role", entity.get("name", "")))).strip().lower()

    if entity_type in {"npc", "creature", "monster", "animal"}:
        if not alive:
            return "corpse"
        if disposition in {"hostile", "afraid"}:
            return "npc_hostile"
        return "npc_friendly"
    if entity_type == "item":
        return "item"
    if template in {"door", "cell_door"}:
        return "door_locked" if locked else "door_unlocked"
    if template in {"gate"}:
        return "gate_locked" if locked else "gate"
    if template in {"chest", "rack", "keys"}:
        if trapped:
            return "chest_trapped"
        return "chest_locked" if locked else "chest"
    if template in _FIXTURE_TEMPLATES:
        return "fixture"
    return _GENERIC_TEMPLATE_TARGET_TYPES.get(template)


def interaction_target_type_for_tile(
    tile: Dict[str, Any],
    *,
    preferred_interaction: InteractionType | None = None,
    rules: Dict[Tuple[str, InteractionType], InteractionRule] | None = None,
    tile_name: str | None = None,
) -> str | None:
    candidates = list(classify_targets(tile, []))
    normalized_name = str(tile_name or "").strip().lower().replace(" ", "_")
    if normalized_name:
        if normalized_name in {"water", "river", "pond"} and "water" not in candidates:
            candidates.insert(0, "water")
        elif normalized_name in {"tree"} and "tree" not in candidates:
            candidates.insert(0, "tree")
        elif normalized_name in {"bridge"} and "bridge" not in candidates:
            candidates.insert(0, "bridge")
        elif normalized_name in {"wall"} and "wall" not in candidates:
            candidates.insert(0, "wall")
        elif normalized_name in {"ore", "ore_vein"} and "ore_vein" not in candidates:
            candidates.insert(0, "ore_vein")
    if preferred_interaction is not None and rules is not None:
        for candidate in candidates:
            if (candidate, preferred_interaction) in rules:
                return candidate
    return candidates[0] if candidates else None


def describe_interactions_for_target(
    target_type: str | None,
    player: Any,
    rules: Dict[Tuple[str, InteractionType], InteractionRule],
) -> List[Dict[str, Any]]:
    if not target_type:
        return []
    descriptors: List[Dict[str, Any]] = []
    for (rule_target, interaction_type), rule in sorted(
        rules.items(),
        key=lambda item: (interaction_type_id(item[0][1]), item[0][0]),
    ):
        if rule_target != target_type:
            continue
        blocked_reason = interaction_block_reason(rule, player)
        governing_check = governing_check_for_rule(interaction_type, rule)
        descriptors.append(
            {
                "id": interaction_type_id(interaction_type),
                "label": interaction_label(interaction_type),
                "interaction_id": interaction_type_id(interaction_type),
                "governing_check": governing_check,
                "requirements": list(rule.get("requirements", [])),
                "ap_cost": int(rule.get("ap_cost", 0)),
                "available": blocked_reason == "",
                "blocked_reason": blocked_reason,
            }
        )
    return descriptors


def primary_interaction_id(
    descriptors: List[Dict[str, Any]],
    context_actions: List[str] | None = None,
) -> str | None:
    canonical_hints = []
    for action in list(context_actions or []):
        normalized = str(action).strip().lower().replace(" ", "_")
        if normalized == "pick_up":
            normalized = "pickup"
        canonical_hints.append(normalized)
    for hint in canonical_hints:
        for descriptor in descriptors:
            if str(descriptor.get("interaction_id", "")) == hint:
                return hint
    for descriptor in descriptors:
        if bool(descriptor.get("available")):
            return str(descriptor.get("interaction_id", ""))
    if descriptors:
        return str(descriptors[0].get("interaction_id", ""))
    return None


def build_skilldex_entries(
    player: Any,
    rules: Dict[Tuple[str, InteractionType], InteractionRule],
) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    entries: List[Dict[str, Any]] = []
    for (_target_type, interaction_type), rule in sorted(
        rules.items(),
        key=lambda item: (interaction_type_id(item[0][1]), item[0][0]),
    ):
        interaction_id = interaction_type_id(interaction_type)
        if interaction_id in seen or interaction_id in _FIXED_VERB_INTERACTION_IDS:
            continue
        governing_check = governing_check_for_rule(interaction_type, rule)
        if not governing_check:
            continue
        seen.add(interaction_id)
        entries.append(
            {
                "id": interaction_id,
                "label": interaction_label(interaction_type),
                "interaction_id": interaction_id,
                "governing_check": governing_check,
                "bonus": interaction_bonus(player, governing_check),
                "requirements": list(rule.get("requirements", [])),
                "proficient": player_has_proficiency(player, governing_check),
                "expertise": player_has_expertise(player, governing_check),
            }
        )
    return entries


def perform_interaction(
    interaction_type: InteractionType,
    player: Any,
    target: Dict[str, Any],
    context: Dict[str, Any],
    rules: Dict[Tuple[str, InteractionType], InteractionRule],
) -> InteractionResult:
    rule = rules.get((str(target.get("target_type", "")).strip(), interaction_type))
    if rule is None:
        return InteractionResult(
            success=False,
            narrative_prompt=f"Cannot {interaction_label(interaction_type).lower()} this target.",
            ap_cost=0,
        )

    blocked_reason = interaction_block_reason(rule, player, target=target)
    if blocked_reason:
        return InteractionResult(
            success=False,
            narrative_prompt=f"Cannot {interaction_label(interaction_type).lower()} {target.get('name', 'that target')}: {blocked_reason}",
            ap_cost=0,
            state_changes={"blocked_reason": blocked_reason},
        )

    handler = InteractionHandler(rules)
    run_context = dict(context)
    run_context.setdefault("rng", Random(int(context.get("seed", 0))))
    return handler.handle(interaction_type, _player_check_payload(player), target, run_context)


def governing_check_for_rule(interaction_type: InteractionType, rule: InteractionRule) -> str | None:
    skill = rule.get("skill")
    if skill in _ABILITY_IDS:
        interaction_id = interaction_type_id(interaction_type)
        skill_map = get_skill_stat_map()
        preferred = _INTERACTION_SKILL_ALIASES.get(interaction_id)
        if preferred and preferred in skill_map and str(skill_map.get(preferred, "")).upper() == str(skill).upper():
            return preferred
        return str(skill)
    if skill:
        return str(skill)
    return None


def interaction_bonus(player: Any, governing_check: str | None) -> int:
    if not governing_check:
        return 0
    if governing_check in _ABILITY_IDS:
        return _player_ability_modifier(player, governing_check)
    if hasattr(player, "skill_bonus"):
        return int(player.skill_bonus(governing_check))
    skills = dict(player.get("skills", {}) or {}) if isinstance(player, dict) else {}
    if governing_check in skills:
        return int(skills[governing_check])
    skill_map = get_skill_stat_map()
    return _player_ability_modifier(player, str(skill_map.get(governing_check, "MIG")).upper())


def player_has_proficiency(player: Any, governing_check: str | None) -> bool:
    if not governing_check or governing_check in _ABILITY_IDS:
        return False
    if hasattr(player, "has_proficiency"):
        return bool(player.has_proficiency(governing_check))
    proficiencies = set(str(item) for item in list(player.get("skill_proficiencies", [])) if isinstance(player, dict))
    return governing_check in proficiencies


def player_has_expertise(player: Any, governing_check: str | None) -> bool:
    if not governing_check or governing_check in _ABILITY_IDS:
        return False
    if hasattr(player, "has_expertise"):
        return bool(player.has_expertise(governing_check))
    expertise = set(str(item) for item in list(player.get("expertise_skills", [])) if isinstance(player, dict))
    return governing_check in expertise


def interaction_block_reason(
    rule: InteractionRule,
    player: Any,
    *,
    target: Dict[str, Any] | None = None,
) -> str:
    for requirement in list(rule.get("requirements", [])):
        reason = requirement_block_reason(str(requirement), player, target=target)
        if reason:
            return reason
    return ""


def requirement_block_reason(requirement: str, player: Any, *, target: Dict[str, Any] | None = None) -> str:
    normalized = str(requirement).strip().lower()
    if not normalized:
        return ""
    if normalized == "gold":
        current_gold = int(getattr(player, "gold", 0) if hasattr(player, "gold") else dict(player).get("gold", 0))
        return "" if current_gold > 0 else "Requires gold."
    if normalized == "ingredients":
        inventory_count = len(getattr(player, "inventory", []) or []) if hasattr(player, "inventory") else len(list(dict(player).get("inventory", [])))
        return "" if inventory_count > 0 else "Requires ingredients."
    if normalized == "matching_key":
        required_key = str((target or {}).get("matching_key", "")).strip().lower()
        if not required_key:
            return "Requires a matching key."
        return "" if required_key in _player_inventory_tokens(player) else "Requires a matching key."
    aliases = _REQUIREMENT_ITEM_ALIASES.get(normalized, {normalized})
    tokens = _player_inventory_tokens(player)
    for alias in aliases:
        if alias in tokens:
            return ""
    label = normalized.replace("_", " ")
    return f"Requires {label}."


def _player_check_payload(player: Any) -> Dict[str, Any]:
    if isinstance(player, dict):
        return player
    abilities = {ability: _player_ability_score(player, ability) for ability in _ABILITY_IDS}
    return {"abilities": abilities}


def _player_ability_score(player: Any, ability: str) -> int:
    if hasattr(player, "stats"):
        return int(getattr(player, "stats", {}).get(ability, 10))
    return int(dict(player).get("abilities", {}).get(ability, 10))


def _player_ability_modifier(player: Any, ability: str) -> int:
    return ability_modifier(_player_ability_score(player, ability))


def _player_inventory_tokens(player: Any) -> set[str]:
    tokens: set[str] = set()
    inventory = list(getattr(player, "inventory", []) or []) if hasattr(player, "inventory") else list(dict(player).get("inventory", []))
    for item in inventory:
        if isinstance(item, dict):
            item_id = str(item.get("item_def_id", item.get("id", ""))).strip().lower()
            name = str(item.get("name", "")).strip().lower().replace(" ", "_")
        else:
            item_id = str(getattr(item, "item_def_id", "")).strip().lower()
            payload = dict(getattr(item, "payload", {}) or {})
            name = str(payload.get("name", item_id)).strip().lower().replace(" ", "_")
        if item_id:
            tokens.add(item_id)
        if name:
            tokens.add(name)
    return tokens


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
