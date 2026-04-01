# PRD: World Data Registries v1
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Define the data registry layout and loader contracts for the world simulation kernel so that world profiles, biomes, species, cultures, building templates, furniture, and adapter packs are explicit, validated, and deterministic.

## 2. Scope
- In scope: JSON registry layout under `frp-backend/data/world`, schema expectations, ID rules, loader behavior, and adapter pack organization.
- Out of scope: client asset generation and non-world gameplay registries such as combat spells.

## 3. Functional Requirements (FR)
FR-01: World simulation content must load from explicit registries under `frp-backend/data/world/`.
FR-02: Registry loading must validate IDs, required fields, duplicate IDs, and cross-file references before generation begins.
FR-03: The first registry pack must include world profiles, biomes, species templates, culture templates, building templates, furniture, and fantasy adapters.
FR-04: Registry helpers must support deterministic loading order and stable dict/list outputs for tests.
FR-05: Registry schemas must be kernel-neutral and avoid hard-coded legacy faction IDs as engine contracts.
FR-06: Building and furniture registries must expose the fields required by settlement realization.

## 4. Data Structures
```python
class RegistryPaths:
    base = "frp-backend/data/world"
    profiles = "profiles.json"
    biomes = "biomes.json"
    species = "species_templates.json"
    cultures = "cultures.json"
    buildings = "building_templates.json"
    furniture = "furniture.json"
    adapters = "adapters/fantasy_ember.json"
```

## 5. Public API
```python
def load_world_profiles() -> dict[str, dict]
def load_world_biomes() -> dict[str, dict]
def load_species_templates() -> dict[str, dict]
def load_culture_templates() -> dict[str, dict]
def load_building_templates() -> dict[str, dict]
def load_furniture_templates() -> dict[str, dict]
def load_adapter_pack(adapter_id: str) -> dict
def validate_world_registries() -> None
```
- Preconditions: JSON files must exist and be valid UTF-8 JSON.
- Postconditions: loaders return normalized dictionaries keyed by stable IDs.
- Exceptions: missing files, invalid schema, and unresolved references raise `ValueError` or `FileNotFoundError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The new world registries exist under `frp-backend/data/world/`.
AC-02 [FR-02]: Duplicate IDs or unresolved references cause validation failure before generation.
AC-03 [FR-03]: The first pack loads profiles, biomes, species, cultures, buildings, furniture, and a fantasy adapter.
AC-04 [FR-04]: Repeated registry loads yield identical normalized key ordering and data values.
AC-05 [FR-05]: No loader requires legacy faction IDs such as `harbor_guard` as engine-level contracts.
AC-06 [FR-06]: Building/furniture registries expose enough data to validate door count, furniture placement, and NPC role binding.

## 7. Performance Requirements
- Full registry validation for the first world pack must complete in under 100 ms.
- Individual registry loads should complete in under 20 ms each.

## 8. Error Handling
- Missing files must raise file-specific errors.
- Malformed JSON must surface the file path and parser error.
- Unresolved adapter references must identify the adapter ID and missing kernel species or tags.

## 9. Integration Points
- Used by all `engine.worldgen` stage entrypoints.
- Replaces mixed legacy world configuration stored in `worldgen.json` and shallow history tables over time.
- Feeds region realization, runtime ticking, and future adapter packs.

## 10. Test Coverage Target
- Minimum 95% coverage on registry loaders and validators.
- Required targeted suite: `test_world_profiles.py`.

## Changelog
- 2026-03-27: Initial PRD for the world registry layer.
