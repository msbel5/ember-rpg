# PRD: Species Lineages and Content Adapters v1
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Model world inhabitants through kernel-native species templates and lineages, then map those lineages into setting-specific content packs such as the fantasy-medieval Ember adapter without baking genre assumptions into the core simulation logic.

## 2. Scope
- In scope: species templates, lineage propagation, sapient vs non-sapient flags, domestication traits, supernatural tags, and adapter mappings.
- Out of scope: tactical combat stats, dialog writing, and a production sci-fi adapter implementation.

## 3. Functional Requirements (FR)
FR-01: Species templates must be defined in kernel-neutral terms: habitat, physiology, cognition, sociality, technology affinity, domestication traits, and supernatural tags.
FR-02: Species lineages must seed into macro regions only where ecology scores them as viable.
FR-03: Sapient lineages must expose the traits needed for culture and civilization seeding.
FR-04: Adapters must map kernel-native species tags into setting-native labels, visuals, and lore handles without mutating the kernel template.
FR-05: The fantasy Ember adapter must map at least humans, dwarves, elves, and dragons from kernel-native lineages.
FR-06: Adapter failures must be explicit and deterministic, with fallback only when the adapter declares a supported fallback.

## 4. Data Structures
```python
@dataclass
class SpeciesTemplate:
    id: str
    name: str
    sapient: bool
    habitats: list[str]
    physiology_tags: list[str]
    cognition_tags: list[str]
    social_structure: str
    domestication_roles: list[str]
    supernatural_tags: list[str]

@dataclass
class SpeciesLineage:
    species_id: str
    home_regions: list[str]
    expansion_regions: list[str]
    adapter_payload: dict
```

## 5. Public API
```python
def seed_lineages(world: WorldBlueprint, species_registry: dict[str, SpeciesTemplate]) -> WorldBlueprint
def adapt_species(world: WorldBlueprint, adapter_id: str) -> WorldBlueprint
def list_adapter_species(adapter_id: str) -> list[str]
```
- Preconditions: species and adapter registries must exist.
- Postconditions: sapient lineages carry adapter-ready payloads for later civilization seeding.
- Exceptions: unknown adapter IDs or unresolved species mappings raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Species templates can be loaded without any fantasy-only required field.
AC-02 [FR-02]: A lineage with only alpine habitat support cannot seed into tropical lowland regions.
AC-03 [FR-03]: Sapient lineages expose enough metadata for culture seeding without reading adapter-only fields.
AC-04 [FR-04]: Applying the fantasy Ember adapter changes labels and payloads, but does not alter the kernel-native species IDs.
AC-05 [FR-05]: The fantasy adapter exposes mapped outputs for humans, dwarves, elves, and dragons.
AC-06 [FR-06]: Unknown adapter IDs raise a deterministic error instead of silently falling back.

## 7. Performance Requirements
- Species seeding plus fantasy adapter mapping for the standard profile must complete in under 250 ms.

## 8. Error Handling
- Invalid species registries must fail validation before world generation begins.
- Adapter mapping collisions must raise errors that identify the conflicting species IDs.
- Non-sapient species may omit civilization-facing fields only when those fields are not required by the kernel template schema.

## 9. Integration Points
- Consumes habitat scores from ecology distribution.
- Supplies sapient candidates to civilization seeding.
- Supplies client-facing display metadata through adapter payloads after realization.

## 10. Test Coverage Target
- Minimum 95% coverage on lineage seeding and adapter resolution.
- Required targeted suite: `test_species_lineages.py`.

## Changelog
- 2026-03-27: Initial PRD for species templates, lineages, and adapters.
