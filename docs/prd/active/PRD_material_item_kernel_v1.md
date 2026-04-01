# PRD: Material and Item Kernel V1
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Material and Item Kernel V1 defines the typed equipment and inventory surface that canonical actors will use. The goal is to replace “bags of dicts” with deterministic, genre-agnostic item and material records that can support damage, quality, wear, coverage, trade value, and crafting outputs.

## 2. Scope
- In scope: typed material definitions, typed item definitions, typed item instances/stacks, slot-based equipment loadout, basic coverage metadata, serialization, adapters from current dict inventory payloads.
- Out of scope: final reaction/crafting economy, deep stack splitting rules, artifact lore, procedural naming, final UI inventory presentation.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M01 Combat, M11 Trade, M17 Wear / Degradation.
- Dependency guardrail: combat force resolution, trade valuation, and wear progression must query the same canonical material and item records.

## 4. Functional Requirements (FR)
FR-01: The backend must define a typed `MaterialDef`.

FR-02: `MaterialDef` must support deterministic combat and crafting fields including:
- density
- impact yield
- impact fracture
- shear yield
- shear fracture
- edge quality

FR-03: The backend must define a typed `ItemDef` describing the reusable template for an item class.

FR-04: `ItemDef` must support genre-agnostic categories and optional equipment slots.

FR-05: The backend must define a typed `ItemStack` / item instance surface for carried or world items.

FR-06: `ItemStack` must preserve quality, wear, quantity, material identity, and arbitrary migration-safe payload.

FR-07: The backend must define an `EquipmentLoadout` that groups equipped items by slot.

FR-08: Coverage data must be explicit so combat and body-state layers can query which parts are protected.

FR-09: Legacy inventory dict entries must be promotable into typed item stacks through an adapter path.

FR-10: Typed item/material records must round-trip through save/load without losing deterministic fields.

## 5. Data Structures
```python
@dataclass
class MaterialDef:
    material_id: str
    label: str
    category: str
    density: int = 0
    impact_yield: int = 0
    impact_fracture: int = 0
    shear_yield: int = 0
    shear_fracture: int = 0
    max_edge: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class ItemDef:
    item_id: str
    label: str
    category: str
    slot: str | None = None
    coverage: list[str] = field(default_factory=list)
    default_material_id: str | None = None
    attack_profile: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class ItemStack:
    instance_id: str
    item_def_id: str
    quantity: int = 1
    material_id: str | None = None
    quality: int = 0
    wear: int = 0
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class EquipmentLoadout:
    slots: dict[str, list[ItemStack]] = field(default_factory=dict)
```

## 6. Public API
```python
def item_stack_from_legacy_payload(payload: dict[str, Any], *, index: int = 0) -> ItemStack
```
- Preconditions: payload may be incomplete or ad hoc.
- Postconditions: a typed stack is always returned, with missing fields preserved inside `payload`.

```python
class EquipmentLoadout:
    def covered_parts(self) -> set[str]: ...
```

## 7. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given a canonical material record, when it is serialized, then density and durability fields remain intact.

AC-02 [FR-03, FR-04]: Given a canonical item definition, when it represents armor or weapons, then slot and coverage metadata are explicit rather than inferred from UI names.

AC-03 [FR-05, FR-06]: Given a carried item stack, when it is serialized and restored, then quantity, quality, wear, material, and payload round-trip.

AC-04 [FR-07, FR-08]: Given a loadout with equipped armor, when covered parts are queried, then the returned set matches the union of equipped item coverage lists.

AC-05 [FR-09]: Given a legacy inventory entry with missing typed fields, when it is adapted, then a stable `ItemStack` is still produced.

AC-06 [FR-10]: Given typed material and item records inside an actor record, when save/load round-trips run, then no dict-only downgrade occurs.

## 8. Error Handling
- Unknown or blank item ids must produce deterministic placeholder ids, not `None`.
- Quantity less than 1 must clamp to 1 during migration.
- Invalid coverage payloads must normalize to empty coverage rather than crash actor conversion.

## 9. Integration Points
- canonical actor kernel
- existing inventory management handlers
- combat damage resolution
- later job/reaction and economy kernels

## 10. Test Coverage Target
- Adapters must cover empty payloads, partial payloads, and equipment payloads.
- Coverage and serialization behavior must have direct tests.
