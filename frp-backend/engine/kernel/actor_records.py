from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.world.body_parts import BodyPartTracker, DEFAULT_PART_HP
from engine.world.entity import Entity

from .actor_body import BodyState, ConditionRecord
from .actor_foundation import ActorIdentity, ActorPosition, NeedState, ScheduleState
from .actor_items import EquipmentLoadout, ItemStack, item_stack_from_legacy_payload


@dataclass
class ActorRecord:
    identity: ActorIdentity
    position: ActorPosition
    action_points: int
    max_action_points: int
    alive: bool
    turn_resources: dict[str, int | bool] = field(default_factory=dict)
    stats: dict[str, int | float] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    needs: NeedState = field(default_factory=NeedState)
    schedule: ScheduleState = field(default_factory=ScheduleState)
    body_state: BodyState | None = None
    inventory: list[ItemStack] = field(default_factory=list)
    equipment: EquipmentLoadout = field(default_factory=EquipmentLoadout)
    conditions: list[ConditionRecord] = field(default_factory=list)
    effect_queue: "EffectQueue | None" = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    # ── Convenience properties for handler compatibility ────────────
    @property
    def name(self) -> str:
        """Display name shortcut."""
        return self.identity.display_name

    @property
    def hp(self) -> int:
        return int(self.stats.get("hp", 0))

    @hp.setter
    def hp(self, value: int) -> None:
        self.stats["hp"] = max(0, int(value))
        if self.stats["hp"] <= 0:
            self.alive = False

    @property
    def max_hp(self) -> int:
        return int(self.stats.get("max_hp", 0))

    @property
    def ac(self) -> int:
        return int(self.raw_payload.get("ac", 10))

    @property
    def level(self) -> int:
        return int(self.raw_payload.get("level", 1))

    def stat_modifier(self, stat: str) -> int:
        """Compute (stat - 10) // 2 for any Ember stat."""
        return (int(self.stats.get(stat, 10)) - 10) // 2

    def skill_bonus(self, skill: str) -> int:
        """Return skill value from skills dict, or stat modifier fallback."""
        if skill in self.skills:
            return int(self.skills[skill])
        # Fallback: governing stat modifier.
        _SKILL_STATS = {"melee": "MIG", "athletics": "MIG", "stealth": "AGI",
                        "acrobatics": "AGI", "perception": "INS", "insight": "INS",
                        "persuasion": "PRE", "intimidation": "PRE", "arcana": "MND",
                        "history": "MND", "medicine": "INS", "survival": "INS"}
        stat = _SKILL_STATS.get(skill, "MIG")
        return self.stat_modifier(stat)

    def to_dict(self) -> dict[str, Any]:
        payload = serialize_value(self)
        payload.pop("action_points", None)
        payload.pop("max_action_points", None)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorRecord":
        payload = dict(data)
        if not isinstance(payload.get("turn_resources"), dict):
            payload["turn_resources"] = _turn_resources_from_legacy_points(
                int(payload.get("action_points", 0) or 0),
                int(payload.get("max_action_points", 0) or 0),
            )
        payload.setdefault("action_points", int(payload["turn_resources"].get("movement_remaining", 0)))
        payload.setdefault("max_action_points", int(payload["turn_resources"].get("speed", 0)))
        payload["identity"] = ActorIdentity.from_dict(payload["identity"])
        payload["position"] = ActorPosition.from_dict(payload["position"])
        needs = payload.get("needs")
        payload["needs"] = NeedState.from_dict(needs) if isinstance(needs, dict) else NeedState()
        schedule = payload.get("schedule")
        payload["schedule"] = ScheduleState.from_dict(schedule) if isinstance(schedule, dict) else ScheduleState()
        body_state = payload.get("body_state")
        payload["body_state"] = BodyState.from_dict(body_state) if body_state else None
        payload["inventory"] = [ItemStack.from_dict(item) for item in payload.get("inventory", [])]
        payload["equipment"] = EquipmentLoadout.from_dict(payload.get("equipment", {}))
        payload["conditions"] = [ConditionRecord.from_dict(item) for item in payload.get("conditions", [])]
        effect_queue = payload.get("effect_queue")
        if isinstance(effect_queue, dict):
            from engine.kernel.effects import EffectQueue

            payload["effect_queue"] = EffectQueue.from_dict(effect_queue)
        return cls(**payload)


def actor_record_from_entity(
    entity: Entity,
    *,
    site_id: str | None = None,
    species_id: str | None = None,
    culture_id: str | None = None,
    region_id: str | None = None,
) -> ActorRecord:
    identity = ActorIdentity(
        actor_id=entity.id,
        display_name=entity.name,
        actor_type=entity.entity_type.value,
        faction_id=entity.faction,
        site_id=site_id,
        species_id=species_id,
        culture_id=culture_id,
    )
    position = ActorPosition(x=int(entity.position[0]), y=int(entity.position[1]), region_id=region_id, site_id=site_id)
    inventory_entries = list(entity.inventory or [])
    inventory = [item_stack_from_legacy_payload(entry, index=index) for index, entry in enumerate(inventory_entries)]
    equipment = EquipmentLoadout()
    for item in inventory:
        slot = str(item.payload.get("slot", item.payload.get("equip_slot", ""))).strip()
        if slot:
            equipment.add_item(slot, item)
    return ActorRecord(
        identity=identity,
        position=position,
        action_points=entity.ap,
        max_action_points=entity.max_ap,
        turn_resources=_turn_resources_from_legacy_points(
            int(getattr(entity, "ap", 0) or 0),
            int(getattr(entity, "max_ap", 0) or 0),
        ),
        alive=entity.alive,
        stats={"hp": entity.hp, "max_hp": entity.max_hp},
        skills=dict(entity.skills or {}),
        needs=NeedState.from_legacy(entity.needs),
        schedule=ScheduleState.from_legacy(entity.schedule),
        body_state=BodyState.from_tracker(entity.body or BodyPartTracker()),
        inventory=inventory,
        equipment=equipment,
        raw_payload={
            "legacy_alignment": entity.alignment,
            "legacy_alignment_axes": dict(entity.alignment_axes or {}),
            "legacy_disposition": entity.disposition,
            "legacy_attitude": entity.attitude,
            "legacy_blocking": entity.blocking,
            "legacy_color": entity.color,
            "legacy_glyph": entity.glyph,
            "legacy_job": entity.job,
        },
    )


def actor_record_from_character(
    character: Any,
    *,
    actor_id: str,
    actor_type: str = "player",
    faction_id: str | None = None,
    site_id: str | None = None,
    region_id: str | None = None,
    position: tuple[int, int] = (0, 0),
    equipment_payloads: dict[str, dict[str, Any] | None] | None = None,
) -> ActorRecord:
    equipment = EquipmentLoadout()
    inventory: list[ItemStack] = []
    for index, (slot, payload) in enumerate((equipment_payloads or {}).items()):
        if not payload:
            continue
        item_payload = dict(payload)
        item_payload.setdefault("slot", slot)
        stack = item_stack_from_legacy_payload(item_payload, index=index)
        equipment.add_item(slot, stack)
        inventory.append(stack)
    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=str(getattr(character, "name", actor_id)),
            actor_type=actor_type,
            faction_id=faction_id,
            site_id=site_id,
        ),
        position=ActorPosition(x=int(position[0]), y=int(position[1]), region_id=region_id, site_id=site_id),
        action_points=int(getattr(character, "ap", 0) or 0),
        max_action_points=int(getattr(character, "max_ap", getattr(character, "ap", 0) or 0) or 0),
        turn_resources=_turn_resources_from_legacy_points(
            int(getattr(character, "ap", 0) or 0),
            int(getattr(character, "max_ap", getattr(character, "ap", 0) or 0) or 0),
        ),
        alive=int(getattr(character, "hp", 0)) > 0,
        stats=dict(getattr(character, "stats", {}) or {}),
        skills=dict(getattr(character, "skills", {}) or {}),
        needs=NeedState(),
        schedule=ScheduleState(),
        body_state=BodyState.from_tracker(BodyPartTracker()),
        inventory=inventory,
        equipment=equipment,
        raw_payload={
            "ac": int(getattr(character, "ac", 10)),
            "alignment": str(getattr(character, "alignment", "TN")),
        },
    )


def sync_body_state_to_tracker(body_state: BodyState, tracker: BodyPartTracker) -> None:
    for part_id, default_hp in DEFAULT_PART_HP.items():
        tracker.max_hp.setdefault(part_id, default_hp)
        tracker.current_hp.setdefault(part_id, default_hp)
    for part_id, state in body_state.parts.items():
        tracker.max_hp[part_id] = int(state.max_hp)
        tracker.current_hp[part_id] = max(0, int(state.current_hp))


def _turn_resources_from_legacy_points(current_points: int, max_points: int) -> dict[str, int | bool]:
    speed = max(6, int(max_points or current_points or 6))
    return {
        "action_available": int(current_points) > 0,
        "bonus_action_available": int(current_points) > 1,
        "reaction_available": True,
        "movement_remaining": max(0, int(current_points or speed)),
        "speed": speed,
    }


# ── Kernel-native factory functions (no legacy Character needed) ──────

# D&D stat name -> Ember stat name mapping for monster templates.
_DND_TO_EMBER = {"str": "MIG", "dex": "AGI", "con": "END", "int": "MND", "wis": "INS", "cha": "PRE"}

# Default HP per class at level 1 (hit_die/2 + 1 + END modifier assumed 0).
_CLASS_HP = {"warrior": 20, "rogue": 16, "mage": 12, "priest": 16, "ranger": 18, "paladin": 20}

# Default BAB rate per class (full=1, 3/4=0.75, 1/2=0.5).
_CLASS_BAB_RATE = {"warrior": 1.0, "rogue": 0.75, "mage": 0.5, "priest": 0.75, "ranger": 1.0, "paladin": 1.0}

_MONSTER_COUNTER = 0


def create_player_actor(
    name: str,
    class_name: str,
    stats: dict[str, int],
    *,
    level: int = 1,
    actor_id: str = "player",
    position: tuple[int, int] = (0, 0),
    skills: dict[str, int] | None = None,
    faction_id: str | None = None,
    region_id: str | None = None,
    site_id: str | None = None,
) -> ActorRecord:
    """Create a player ActorRecord directly from creation data.

    No legacy Character object is needed. Stats must use Ember keys
    (MIG/AGI/END/MND/INS/PRE).
    """
    # Ensure all six Ember stats are present.
    full_stats = dict(stats)
    for key in ("MIG", "AGI", "END", "MND", "INS", "PRE"):
        full_stats.setdefault(key, 10)

    # Calculate HP from class defaults + END modifier.
    end_mod = (int(full_stats.get("END", 10)) - 10) // 2
    base_hp = _CLASS_HP.get(class_name.lower(), 16)
    hp = max(1, base_hp + end_mod)
    full_stats["hp"] = hp
    full_stats["max_hp"] = hp

    # Calculate BAB from class and level.
    bab_rate = _CLASS_BAB_RATE.get(class_name.lower(), 0.75)
    bab = max(0, int(level * bab_rate))

    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=name,
            actor_type="pc",
            faction_id=faction_id,
            site_id=site_id,
        ),
        position=ActorPosition(x=int(position[0]), y=int(position[1]), region_id=region_id, site_id=site_id),
        action_points=6,
        max_action_points=6,
        alive=True,
        stats=full_stats,
        skills=dict(skills or {}),
        body_state=BodyState.from_tracker(BodyPartTracker()),
        raw_payload={
            "class_name": class_name.lower(),
            "level": level,
            "bab": bab,
            "bab_rate": bab_rate,
        },
    )


def create_monster_actor(
    template: dict[str, Any],
    *,
    position: tuple[int, int] = (0, 0),
    faction_id: str = "hostile",
    region_id: str | None = None,
    site_id: str | None = None,
) -> ActorRecord:
    """Create a monster ActorRecord directly from a JSON template.

    Maps D&D stat keys (str/dex/con/int/wis/cha) to Ember keys
    (MIG/AGI/END/MND/INS/PRE).
    """
    global _MONSTER_COUNTER
    _MONSTER_COUNTER += 1

    # Map stats from template (D&D lowercase -> Ember uppercase).
    raw_stats = dict(template.get("stats", {}))
    ember_stats: dict[str, int | float] = {}
    for dnd_key, ember_key in _DND_TO_EMBER.items():
        ember_stats[ember_key] = int(raw_stats.get(dnd_key, 10))

    hp = int(template.get("hp", 10))
    ember_stats["hp"] = hp
    ember_stats["max_hp"] = hp

    # Extract attack bonus from first attack entry.
    attacks = list(template.get("attacks", []))
    first_attack = attacks[0] if attacks else {}
    attack_bonus = int(first_attack.get("attack_bonus", 2))
    mig_mod = (int(ember_stats.get("MIG", 10)) - 10) // 2
    melee_skill = max(0, attack_bonus - mig_mod)

    # Estimate BAB from CR.
    cr = float(template.get("cr", 1.0))
    bab = max(1, int(cr * 2))

    actor_id = f"{template.get('id', 'monster')}_{_MONSTER_COUNTER}"

    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=str(template.get("name", "Monster")),
            actor_type="npc",
            faction_id=faction_id,
            site_id=site_id,
        ),
        position=ActorPosition(x=int(position[0]), y=int(position[1]), region_id=region_id, site_id=site_id),
        action_points=6,
        max_action_points=6,
        alive=True,
        stats=ember_stats,
        skills={"melee": melee_skill},
        body_state=BodyState.from_tracker(BodyPartTracker()),
        raw_payload={
            "monster_id": str(template.get("id", "")),
            "monster_type": str(template.get("type", "monster")),
            "cr": cr,
            "bab": bab,
            "ac": int(template.get("armor_class", 10)),
            "attacks": attacks,
            "loot_table": list(template.get("loot_table", [])),
        },
    )


__all__ = [
    "ActorRecord",
    "actor_record_from_character",
    "actor_record_from_entity",
    "create_monster_actor",
    "create_player_actor",
    "sync_body_state_to_tracker",
]
