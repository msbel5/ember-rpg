"""Kernel ActorRecord — single source of truth for all actor data.

Every actor in Ember (player, NPC, monster) is an ActorRecord.  The
dataclass fields hold structured kernel types; ``raw_payload`` is a
free-form dict that stores RPG metadata written at creation time
(class_name, level, alignment, creation_profile, …).

Properties expose raw_payload values through a typed API so that
session, serialization and settlement code can read them without
reaching into the dict directly.  Setters write back into raw_payload
so round-tripping through to_dict/from_dict is lossless.

Design rules
────────────
• No legacy shims — consumers speak kernel types.
• ``inventory`` is ``list[ItemStack]``.
• ``equipment`` is ``EquipmentLoadout``.
• ``conditions`` is ``list[ConditionRecord]``.
• RPG scalars (ac, xp, gold, …) live in ``raw_payload``.
• ``stats`` holds the six Ember abilities + hp/max_hp.
"""
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
    """Core actor model for the kernel-only architecture."""

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

    # ── Identity / display ─────────────────────────────────────
    @property
    def name(self) -> str:
        return self.identity.display_name

    # ── Combat stats (backed by stats dict) ────────────────────
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

    @max_hp.setter
    def max_hp(self, value: int) -> None:
        self.stats["max_hp"] = max(0, int(value))

    @property
    def ac(self) -> int:
        return int(self.raw_payload.get("ac", 10))

    @ac.setter
    def ac(self, value: int) -> None:
        self.raw_payload["ac"] = int(value)

    @property
    def base_ac(self) -> int:
        return int(self.raw_payload.get("base_ac", self.ac))

    @base_ac.setter
    def base_ac(self, value: int) -> None:
        self.raw_payload["base_ac"] = int(value)

    # ── Action points (kernel fields) ──────────────────────────
    @property
    def ap(self) -> int:
        return self.action_points

    @ap.setter
    def ap(self, value: int) -> None:
        self.action_points = int(value)

    @property
    def max_ap(self) -> int:
        return self.max_action_points

    @max_ap.setter
    def max_ap(self, value: int) -> None:
        self.max_action_points = int(value)

    # ── Class / progression (raw_payload) ──────────────────────
    @property
    def level(self) -> int:
        return int(self.raw_payload.get("level", 1))

    @property
    def player_class(self) -> str:
        """Class name from raw_payload, falling back to creation data default."""
        stored = self.raw_payload.get("class_name")
        if stored:
            return str(stored)
        from engine.data.classes import get_creation_default_class
        return get_creation_default_class()

    @property
    def dominant_class(self) -> str:
        return self.player_class

    @property
    def classes(self) -> dict[str, int]:
        cls = self.player_class
        if cls:
            return {cls: self.level}
        from engine.data.classes import get_creation_default_class
        return {get_creation_default_class(): 1}

    @property
    def xp(self) -> int:
        return int(self.raw_payload.get("xp", 0))

    @xp.setter
    def xp(self, value: int) -> None:
        self.raw_payload["xp"] = int(value)

    @property
    def proficiency_bonus(self) -> int:
        return 2 + (self.level - 1) // 4

    # ── Resource pools (raw_payload) ───────────────────────────
    @property
    def spell_points(self) -> int:
        return int(self.raw_payload.get("spell_points", 0))

    @spell_points.setter
    def spell_points(self, value: int) -> None:
        self.raw_payload["spell_points"] = int(value)

    @property
    def max_spell_points(self) -> int:
        return int(self.raw_payload.get("max_spell_points", 0))

    @property
    def gold(self) -> int:
        return int(self.raw_payload.get("gold", 0))

    @gold.setter
    def gold(self, value: int) -> None:
        self.raw_payload["gold"] = int(value)

    # ── Character identity (raw_payload) ───────────────────────
    @property
    def race(self) -> str:
        return str(self.raw_payload.get("race", "human"))

    @property
    def alignment(self) -> str:
        return str(self.raw_payload.get("alignment",
                   self.raw_payload.get("legacy_alignment", "TN")))

    @property
    def alignment_axes(self) -> dict[str, Any]:
        return dict(self.raw_payload.get("alignment_axes",
                    self.raw_payload.get("legacy_alignment_axes", {})))

    # ── Skills & proficiency (raw_payload + skills dict) ───────
    @property
    def skill_proficiencies(self) -> list[str]:
        return list(self.raw_payload.get("skill_proficiencies", []))

    @property
    def expertise_skills(self) -> list[str]:
        return list(self.raw_payload.get("expertise_skills", []))

    def stat_modifier(self, stat: str) -> int:
        """(stat_value - 10) // 2 for any Ember stat."""
        return (int(self.stats.get(stat, 10)) - 10) // 2

    def skill_bonus(self, skill: str) -> int:
        """Skill value from skills dict, falling back to stat modifier.

        The skill→governing-ability map is loaded from
        character_creation.json via get_skill_stat_map().
        """
        if skill in self.skills:
            return int(self.skills[skill])
        from engine.data.classes import get_skill_stat_map
        skill_map = get_skill_stat_map()
        return self.stat_modifier(skill_map.get(skill, "MIG"))

    def has_proficiency(self, skill: str) -> bool:
        return skill in self.skill_proficiencies

    def has_expertise(self, skill: str) -> bool:
        return skill in self.expertise_skills

    @property
    def initiative_bonus(self) -> int:
        return self.stat_modifier("AGI")

    # ── Equipment meta (written by session sync) ───────────────
    @property
    def equipped_armor(self) -> list[str]:
        return list(self.raw_payload.get("equipped_armor", []))

    @equipped_armor.setter
    def equipped_armor(self, value: list[str]) -> None:
        self.raw_payload["equipped_armor"] = list(value)

    @property
    def weapon_material(self) -> str:
        return str(self.raw_payload.get("weapon_material", "iron"))

    @weapon_material.setter
    def weapon_material(self, value: str) -> None:
        self.raw_payload["weapon_material"] = str(value)

    # ── Passives / creation data (raw_payload) ─────────────────
    @property
    def passives(self) -> dict[str, int]:
        return dict(self.raw_payload.get("passives", {}))

    @property
    def creation_profile(self) -> dict[str, Any]:
        return dict(self.raw_payload.get("creation_profile", {}))

    @property
    def creation_answers(self) -> list[Any]:
        return list(self.raw_payload.get("creation_answers", []))

    # ── Hit dice / exhaustion / death saves (raw_payload) ──────
    @property
    def hit_die_size(self) -> int:
        """Hit die size from raw_payload, falling back to class data."""
        stored = self.raw_payload.get("hit_die_size")
        if stored is not None:
            return int(stored)
        from engine.data.classes import get_class_hit_die_size
        return get_class_hit_die_size(self.player_class) or 8

    @property
    def hit_dice_total(self) -> int:
        return int(self.raw_payload.get("hit_dice_total", self.level))

    @property
    def hit_dice_remaining(self) -> int:
        return int(self.raw_payload.get("hit_dice_remaining", self.level))

    @property
    def exhaustion_level(self) -> int:
        return int(self.raw_payload.get("exhaustion_level", 0))

    @property
    def death_save_successes(self) -> int:
        return int(self.raw_payload.get("death_save_successes", 0))

    @property
    def death_save_failures(self) -> int:
        return int(self.raw_payload.get("death_save_failures", 0))

    @property
    def is_stable(self) -> bool:
        return bool(self.raw_payload.get("is_stable", False))

    # ── Condition helpers ──────────────────────────────────────
    @property
    def condition_names(self) -> list[str]:
        """Flat list of active condition names for serialization."""
        return [c.name for c in self.conditions]

    def set_conditions_from_names(self, names: list[str]) -> None:
        """Replace conditions from a flat name list.

        Preserves existing ConditionRecords whose name matches;
        creates minimal records for new names.
        """
        existing = {c.name: c for c in self.conditions}
        result: list[ConditionRecord] = []
        for n in names:
            if n in existing:
                result.append(existing[n])
            else:
                result.append(ConditionRecord(condition_id=n, name=n))
        self.conditions = result

    # ── Serialization ──────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        payload = serialize_value(self)
        payload.pop("action_points", None)
        payload.pop("max_action_points", None)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorRecord":
        payload = dict(data)
        # Turn resources
        if not isinstance(payload.get("turn_resources"), dict):
            payload["turn_resources"] = _turn_resources_from_legacy_points(
                int(payload.get("action_points", 0) or 0),
                int(payload.get("max_action_points", 0) or 0),
            )
        payload.setdefault("action_points",
                           int(payload["turn_resources"].get("movement_remaining", 0)))
        payload.setdefault("max_action_points",
                           int(payload["turn_resources"].get("speed", 0)))

        # Structured sub-objects
        payload["identity"] = ActorIdentity.from_dict(payload["identity"])
        payload["position"] = ActorPosition.from_dict(payload["position"])
        needs = payload.get("needs")
        payload["needs"] = NeedState.from_dict(needs) if isinstance(needs, dict) else NeedState()
        schedule = payload.get("schedule")
        payload["schedule"] = (ScheduleState.from_dict(schedule)
                               if isinstance(schedule, dict) else ScheduleState())
        body_state = payload.get("body_state")
        payload["body_state"] = BodyState.from_dict(body_state) if body_state else None

        # Inventory — handle list[dict] and list[str] (legacy save format)
        raw_inv = payload.get("inventory", [])
        inv: list[ItemStack] = []
        for idx, item in enumerate(raw_inv):
            if isinstance(item, dict):
                inv.append(ItemStack.from_dict(item))
            elif isinstance(item, str):
                inv.append(item_stack_from_legacy_payload(
                    {"id": item, "name": item}, index=idx))
        payload["inventory"] = inv

        payload["equipment"] = EquipmentLoadout.from_dict(
            payload.get("equipment", {}))

        # Conditions — handle list[dict] and list[str]
        raw_conds = payload.get("conditions", [])
        conds: list[ConditionRecord] = []
        for c in raw_conds:
            if isinstance(c, dict):
                conds.append(ConditionRecord.from_dict(c))
            elif isinstance(c, str):
                conds.append(ConditionRecord(condition_id=c, name=c))
        payload["conditions"] = conds

        effect_queue = payload.get("effect_queue")
        if isinstance(effect_queue, dict):
            from engine.kernel.effects import EffectQueue
            payload["effect_queue"] = EffectQueue.from_dict(effect_queue)

        return cls(**payload)


# ── Factory: Entity → ActorRecord ──────────────────────────────

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
    position = ActorPosition(
        x=int(entity.position[0]),
        y=int(entity.position[1]),
        region_id=region_id,
        site_id=site_id,
    )
    inventory_entries = list(entity.inventory or [])
    inventory = [
        item_stack_from_legacy_payload(entry, index=idx)
        for idx, entry in enumerate(inventory_entries)
    ]
    equipment = EquipmentLoadout()
    for item in inventory:
        slot = str(item.payload.get("slot",
                   item.payload.get("equip_slot", ""))).strip()
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
        body_state=BodyState.from_tracker(
            entity.body or BodyPartTracker()),
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


# ── Factory: legacy Character → ActorRecord ────────────────────

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
    for idx, (slot, payload) in enumerate((equipment_payloads or {}).items()):
        if not payload:
            continue
        item_payload = dict(payload)
        item_payload.setdefault("slot", slot)
        stack = item_stack_from_legacy_payload(item_payload, index=idx)
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
        position=ActorPosition(
            x=int(position[0]), y=int(position[1]),
            region_id=region_id, site_id=site_id,
        ),
        action_points=int(getattr(character, "ap", 0) or 0),
        max_action_points=int(
            getattr(character, "max_ap",
                    getattr(character, "ap", 0) or 0) or 0),
        turn_resources=_turn_resources_from_legacy_points(
            int(getattr(character, "ap", 0) or 0),
            int(getattr(character, "max_ap",
                        getattr(character, "ap", 0) or 0) or 0),
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


def sync_body_state_to_tracker(
    body_state: BodyState, tracker: BodyPartTracker,
) -> None:
    for part_id, default_hp in DEFAULT_PART_HP.items():
        tracker.max_hp.setdefault(part_id, default_hp)
        tracker.current_hp.setdefault(part_id, default_hp)
    for part_id, state in body_state.parts.items():
        tracker.max_hp[part_id] = int(state.max_hp)
        tracker.current_hp[part_id] = max(0, int(state.current_hp))


def _turn_resources_from_legacy_points(
    current_points: int, max_points: int,
) -> dict[str, int | bool]:
    speed = max(6, int(max_points or current_points or 6))
    return {
        "action_available": int(current_points) > 0,
        "bonus_action_available": int(current_points) > 1,
        "reaction_available": True,
        "movement_remaining": max(0, int(current_points or speed)),
        "speed": speed,
    }


# ── Kernel-native factories (no legacy Character needed) ───────

# ── Data-driven lookups (no hardcoded game values) ─────────────

def _stat_key_mapping() -> dict[str, str]:
    """D&D→Ember stat key map loaded from character_creation.json."""
    from engine.data.classes import get_stat_key_mapping
    return get_stat_key_mapping()


def _class_default_hp(class_name: str) -> int:
    """Default HP for a class loaded from classes.json."""
    from engine.data.classes import get_class_default_hp
    hp = get_class_default_hp(class_name)
    return hp if hp > 0 else 16  # fallback only when data missing


def _class_hit_die_size(class_name: str) -> int:
    """Hit die size for a class loaded from classes.json."""
    from engine.data.classes import get_class_hit_die_size
    size = get_class_hit_die_size(class_name)
    return size if size > 0 else 8  # fallback only when data missing


def _class_bab_rate(class_name: str) -> float:
    """BAB rate derived from class hp_per_level in progression.json.

    Full martial (hp_per_level >= 10) → 1.0
    Mid martial (hp_per_level >= 8)  → 0.75
    Caster (hp_per_level < 8)        → 0.5
    """
    from engine.data.runtime import get_hp_per_level
    hp_table = get_hp_per_level()
    hp_val = hp_table.get(class_name.lower(), 8)
    if hp_val >= 10:
        return 1.0
    if hp_val >= 8:
        return 0.75
    return 0.5
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

    Stats must use Ember keys (MIG/AGI/END/MND/INS/PRE).
    """
    full_stats = dict(stats)
    for key in ("MIG", "AGI", "END", "MND", "INS", "PRE"):
        full_stats.setdefault(key, 10)

    # HP derived from class data (classes.json) + END modifier
    end_mod = (int(full_stats.get("END", 10)) - 10) // 2
    base_hp = _class_default_hp(class_name)
    hp = max(1, base_hp + end_mod)
    full_stats["hp"] = hp
    full_stats["max_hp"] = hp

    # BAB rate derived from progression.json hp_per_level
    bab_rate = _class_bab_rate(class_name)
    bab = max(0, int(level * bab_rate))

    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=name,
            actor_type="pc",
            faction_id=faction_id,
            site_id=site_id,
        ),
        position=ActorPosition(
            x=int(position[0]), y=int(position[1]),
            region_id=region_id, site_id=site_id,
        ),
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
            "hit_die_size": _class_hit_die_size(class_name),
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
    """Create a monster ActorRecord from a JSON template.

    Maps D&D stat keys to Ember keys.
    """
    global _MONSTER_COUNTER
    _MONSTER_COUNTER += 1

    # Map D&D stat keys → Ember keys via character_creation.json
    raw_stats = dict(template.get("stats", {}))
    stat_mapping = _stat_key_mapping()
    ember_stats: dict[str, int | float] = {}
    for dnd_key, ember_key in stat_mapping.items():
        ember_stats[ember_key] = int(raw_stats.get(dnd_key, 10))

    hp = int(template.get("hp", 10))
    ember_stats["hp"] = hp
    ember_stats["max_hp"] = hp

    attacks = list(template.get("attacks", []))
    first_attack = attacks[0] if attacks else {}
    attack_bonus = int(first_attack.get("attack_bonus", 2))
    mig_mod = (int(ember_stats.get("MIG", 10)) - 10) // 2
    melee_skill = max(0, attack_bonus - mig_mod)

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
        position=ActorPosition(
            x=int(position[0]), y=int(position[1]),
            region_id=region_id, site_id=site_id,
        ),
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
