# PRD: Body, Injury, and Combat Kernel V1
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Body, Injury, and Combat Kernel V1 defines the typed physical state used by actors during combat and injury resolution. The goal is to move beyond a flat per-part HP tracker and establish a body-state surface that can later support layered damage, bleeding, pain, crippled limbs, equipment coverage, and deterministic death checks.

## 2. Scope
- In scope: body plans, body parts, tissue layers, body-state snapshots, wound records, condition records, simplified deterministic combat resolution, migration from `BodyPartTracker`.
- Out of scope: complete Dwarf Fortress-style tissue penetration, infection simulation, surgery, prosthetics, severed part item generation, temperature/syndrome systems.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M01 Combat, M05 Medical, M06 Syndrome / Poison, M17 Wear / Degradation, M18 Military.
- Dependency guardrail: combat must still emit wounds and viability changes that later feed medical, syndrome, morale, and equipment degradation systems.

## 4. Functional Requirements (FR)
FR-01: The backend must define `BodyPlanDef`, `BodyPartDef`, and `TissueLayerDef`.

FR-02: The backend must define a typed `BodyState` containing per-part health state and a wound list.

FR-03: `BodyState` must preserve vital-part semantics explicitly rather than hard-coding them in unrelated combat handlers.

FR-04: The backend must define `WoundRecord` and `ConditionRecord`.

FR-05: The kernel must support migration from legacy `BodyPartTracker` without losing current HP and visible injury state.

FR-06: Simplified deterministic combat resolution must query:
- hit part
- armor coverage
- material durability
- damage type
- resulting wound and part state

FR-07: The first canonical combat layer must support at least:
- blunt damage
- cut damage
- stab/pierce damage

FR-08: Destroyed vital parts must mark the actor non-viable in a typed way.

FR-09: The kernel must preserve current lightweight combat APIs by exposing adapters or façades rather than requiring a full system rewrite in one sprint.

## 5. Data Structures
```python
@dataclass
class TissueLayerDef:
    layer_id: str
    material_id: str
    relative_thickness: int = 1
    structural: bool = False
    under_pressure: bool = False
    cosmetic: bool = False


@dataclass
class BodyPartDef:
    part_id: str
    label: str
    max_hp: int
    vital: bool = False
    parent_id: str | None = None
    layers: list[TissueLayerDef] = field(default_factory=list)


@dataclass
class BodyPlanDef:
    plan_id: str
    label: str
    parts: list[BodyPartDef]


@dataclass
class WoundRecord:
    wound_id: str
    body_part_id: str
    damage_type: str
    damage_amount: int
    bleeding: int = 0
    pain: int = 0
    destroyed: bool = False


@dataclass
class BodyState:
    plan_id: str
    parts: dict[str, BodyPartState]
    wounds: list[WoundRecord] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)
```

## 6. Public API
```python
class BodyState:
    @classmethod
    def from_tracker(cls, tracker: BodyPartTracker, *, plan_id: str = "legacy_humanoid") -> "BodyState": ...
    def apply_wound(self, wound: WoundRecord) -> None: ...
    def is_viable(self) -> bool: ...
```

```python
def resolve_simplified_strike(
    *,
    body_state: BodyState,
    hit_part_id: str,
    damage_type: str,
    base_damage: int,
    armor_reduction: int = 0,
) -> WoundRecord
```

## 7. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given a canonical body plan, when a body state is instantiated, then every defined part has typed current/max HP state.

AC-02 [FR-03]: Given a body plan with vital parts, when those parts are destroyed, then `BodyState.is_viable()` returns false.

AC-03 [FR-04]: Given combat damage is applied, when the result is recorded, then a typed wound record exists with part id, damage type, and damage amount.

AC-04 [FR-05]: Given a legacy `BodyPartTracker`, when it is converted, then current part HP and visible injury statuses are preserved.

AC-05 [FR-06, FR-07]: Given armor reduction and a damage type, when a strike resolves, then the resulting wound reflects the reduced damage deterministically.

AC-06 [FR-08]: Given a destroyed chest, neck, or head-equivalent vital part, when viability is queried, then the actor is no longer viable.

AC-07 [FR-09]: Given existing combat handlers still use legacy surfaces, when the canonical body state is introduced, then migration adapters exist and tests continue to pass without a full combat-engine rewrite.

## 8. Error Handling
- Unknown part ids must raise `ValueError`.
- Negative damage amounts must clamp to zero during resolution.
- Invalid damage types must fail fast instead of silently defaulting.

## 9. Integration Points
- `frp-backend/engine/world/body_parts.py`
- `frp-backend/engine/api/handlers/combat_actions.py`
- canonical actor kernel
- future material/item kernel

## 10. Test Coverage Target
- Migration from `BodyPartTracker`
- vital-part viability rules
- wound serialization
- deterministic strike resolution with and without armor
