# PRD: Canonical Actor Kernel V1
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Canonical Actor Kernel V1 defines the authoritative root model for every simulated being in Ember RPG. The goal is to stop treating player characters, NPCs, creatures, and “special-case world actors” as adjacent but incompatible structures and instead move them under a single typed record that can survive save/load, combat, needs, scheduling, and world-state integration.

## 2. Scope
- In scope: root actor identity, location, faction/site/species links, AP state, typed body linkage, typed inventory linkage, typed needs/schedule snapshots, serialization, adapters from the legacy `Entity` surface.
- Out of scope: full AI conversation state, quest state, colony job queues, deep skill rust rules, final combat math, rendering payloads.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M02 Skill / Learning, M03 Need / Happiness / Stress, M12 Migration / Population, M18 Military.
- Dependency guardrail: the same root actor record must be reusable by combat, jobs, needs, schedules, migration, and future squad logic without introducing separate actor roots.

## 4. Functional Requirements (FR)
FR-01: The backend must define a single canonical root type named `ActorRecord`.

FR-02: `ActorRecord` must be usable for:
- player-controlled commander avatars
- non-player people
- hostile and neutral creatures
- future world-history figures represented in active simulation

FR-03: `ActorRecord` must embed a typed `ActorIdentity` structure containing at least:
- canonical actor id
- display name
- actor type
- faction id
- site id
- species id
- optional culture id

FR-04: `ActorRecord` must carry deterministic location and AP state independently of UI payload shape.

FR-05: `ActorRecord` must reference typed body state rather than using `BodyPartTracker` as the long-term authoritative injury surface.

FR-06: `ActorRecord` must store inventory as typed item instances rather than raw dict lists.

FR-07: `ActorRecord` must preserve legacy data not yet migrated through an explicit `raw_payload` or façade field rather than silently dropping it.

FR-08: The kernel must expose adapters from the current `engine.world.entity.Entity` model so migration can happen incrementally.

FR-09: The same adapter surface must work for both NPC and creature entities without branching into different root record types.

FR-10: `ActorRecord` and its nested records must support deterministic `to_dict()` and `from_dict()` round-trips for save/load migration work.

## 5. Data Structures
```python
@dataclass
class ActorIdentity:
    actor_id: str
    display_name: str
    actor_type: str
    faction_id: str | None = None
    site_id: str | None = None
    species_id: str | None = None
    culture_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ActorPosition:
    x: int
    y: int
    z: int = 0
    region_id: str | None = None
    site_id: str | None = None


@dataclass
class ActorRecord:
    identity: ActorIdentity
    position: ActorPosition
    action_points: int
    max_action_points: int
    alive: bool
    stats: dict[str, int | float] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    needs: dict[str, float] = field(default_factory=dict)
    schedule: dict[str, Any] = field(default_factory=dict)
    body_state: BodyState | None = None
    inventory: list[ItemStack] = field(default_factory=list)
    equipment: EquipmentLoadout = field(default_factory=EquipmentLoadout)
    conditions: list[ConditionRecord] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
```

## 6. Public API
```python
def actor_record_from_entity(
    entity: Entity,
    *,
    site_id: str | None = None,
    species_id: str | None = None,
    culture_id: str | None = None,
) -> ActorRecord
```
- Preconditions: A legacy `Entity` exists.
- Postconditions: A typed canonical actor record is produced without losing legacy alignment/disposition metadata.

```python
class ActorRecord:
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorRecord": ...
```

## 7. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given a player avatar, an NPC, and a creature, when each is converted into canonical state, then each is represented by `ActorRecord` rather than separate root classes.

AC-02 [FR-03]: Given a legacy `Entity` with faction and species context, when it is adapted, then `ActorIdentity` preserves those links in typed fields.

AC-03 [FR-04]: Given an entity with AP and position state, when it is adapted, then those values are available without reading UI or save façades.

AC-04 [FR-05]: Given a legacy `BodyPartTracker`, when the entity is adapted, then a typed `BodyState` exists and remains serializable.

AC-05 [FR-06]: Given a legacy entity inventory composed of raw dict entries, when it is adapted, then each item is promoted into a typed `ItemStack`.

AC-06 [FR-07]: Given legacy fields that do not yet have canonical homes, when the entity is adapted, then those fields remain preserved inside `raw_payload`.

AC-07 [FR-08, FR-09]: Given both an NPC entity and a creature entity, when the same adapter function is called, then both conversions succeed without entity-type-specific root records.

AC-08 [FR-10]: Given a canonical actor record, when it is serialized and reloaded, then identity, body, inventory, and AP state round-trip without loss.

## 8. Error Handling
- Unknown actor types must fail fast with explicit `ValueError`.
- Invalid position payloads must fail fast during `from_dict`.
- Malformed legacy inventory entries must be wrapped into placeholder typed stacks rather than crash unrelated actor migration flows.

## 9. Integration Points
- `frp-backend/engine/world/entity.py`
- `frp-backend/engine/world/body_parts.py`
- `frp-backend/engine/world/npc_needs.py`
- `frp-backend/engine/world/schedules.py`
- future save/load adapters under `engine/api/save/`

## 10. Test Coverage Target
- New kernel adapter tests must cover NPC, creature, and avatar-style inputs.
- Serialization coverage for `ActorRecord` and nested records must be explicit rather than incidental.
