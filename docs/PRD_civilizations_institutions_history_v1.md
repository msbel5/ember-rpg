# PRD: Civilizations, Institutions, and History v1
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Seed cultures and factions from viable sapient lineages, grow institutions and settlements over time, and simulate present-day history from migration, trade, disasters, religion, and war instead of shallow pre-authored history tables.

## 2. Scope
- In scope: culture templates, faction seeds, settlement founding, institution growth, historical events, tensions, and present-day world-state consequences.
- Out of scope: local NPC schedules, tactical combat, and front-end storytelling.

## 3. Functional Requirements (FR)
FR-01: Civilization seeding must found factions and settlements only in regions that satisfy ecology, resource, and species viability constraints.
FR-02: Culture templates must define values, ethics, governance tendencies, technology affinity, and institution biases in a data-driven way.
FR-03: Historical simulation must generate migrations, trade links, wars, disasters, religious shifts, and institutional changes between seed year and present year.
FR-04: Historical events must write durable consequences into faction strength, settlement status, infrastructure, and world tensions.
FR-05: Present-day factions and settlements must be outputs of simulation rather than fixed IDs baked into code.
FR-06: The event ledger must remain deterministic for the same world and end year.
FR-07: Historical outputs must provide enough structure for runtime world-state APIs and quest generation.

## 4. Data Structures
```python
@dataclass
class CultureTemplate:
    id: str
    values: dict[str, int]
    ethics: dict[str, str]
    governance_bias: str
    institution_bias: dict[str, float]

@dataclass
class FactionSeed:
    id: str
    culture_id: str
    species_id: str
    origin_region_id: str
    traits: dict[str, float]

@dataclass
class HistoricalEvent:
    year: int
    event_type: str
    factions: list[str]
    regions: list[str]
    summary: str
    consequences: dict
```

## 5. Public API
```python
def seed_civilizations(world: WorldBlueprint) -> WorldBlueprint
def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint
def list_present_factions(world: WorldBlueprint) -> list[dict]
def list_historical_events(world: WorldBlueprint, limit: int | None = None) -> list[HistoricalEvent]
```
- Preconditions: sapient lineages and culture templates must exist.
- Postconditions: `world.factions`, `world.settlements`, and `world.historical_events` are populated deterministically.
- Exceptions: no viable sapient lineages or invalid culture mappings raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Faction seeds are created only in viable source regions and reference valid lineages and cultures.
AC-02 [FR-02]: Culture templates can express ethics and values without relying on legacy hard-coded faction IDs.
AC-03 [FR-03]: A standard-profile simulated history yields at least one migration/trade event and one conflict/disaster event.
AC-04 [FR-04]: Historical events update at least one present-day faction or settlement field.
AC-05 [FR-05]: Present-day faction IDs differ across different world seeds.
AC-06 [FR-06]: Re-running `simulate_history` with the same world and `end_year` produces identical event ledgers.

## 7. Performance Requirements
- Civilization seeding must complete in under 250 ms for the standard profile.
- History simulation to the default present year must complete in under 2 seconds for the standard profile.

## 8. Error Handling
- Worlds with no viable sapient lineages must fail before history simulation starts.
- Invalid culture references or circular settlement dependencies must raise deterministic validation errors.
- Event generation conflicts must be resolved deterministically, then recorded in debug metadata.

## 9. Integration Points
- Consumes sapient lineages and ecological viability outputs.
- Feeds runtime world-state routes, rumor systems, quest generation, and region realization.
- Replaces shallow legacy history tables and fixed faction assumptions.

## 10. Test Coverage Target
- Minimum 95% coverage on civilization seeding and history simulation helpers.
- Required targeted suites: `test_civilization_seed.py` and `test_history_simulation.py`.

## Changelog
- 2026-03-27: Initial PRD for civilization and history simulation.
