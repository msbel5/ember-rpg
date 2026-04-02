# PRD: Campaign Save Schema V3
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-04-03  
**Status:** Implemented  

---

## 1. Purpose
Define the campaign-only save format used by the shipped runtime. Save schema v3 must store one canonical campaign root and must intentionally reject old mixed legacy/kernel payload layouts.

## 2. Scope
- In scope: schema version bump, canonical campaign root, validation, metadata discovery, save/load round-trip tests, validation failure tracing.
- Out of scope: migration code for schema v2 or legacy session saves.

## 3. Functional Requirements (FR)
FR-01: The current save schema version must be `3.0`.
FR-02: Campaign saves must persist one canonical `campaign_state["campaign"]` root that includes world snapshot, kernel state slices, settlement state, and event history.
FR-03: Session serialization must stop mirroring kernel payloads into top-level `kernel_*` roots.
FR-04: Campaign load must reject saves missing the v3 campaign root.
FR-05: Save validation failures must emit structured debug traces.

## 4. Data Structures
```python
class CampaignSaveRoot(TypedDict):
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int
    active_region_id: str
    world_snapshot: dict[str, Any]
    world_state: dict[str, Any]
    game_state: dict[str, Any]
    actors: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    reactions: list[dict[str, Any]]
    worksites: list[dict[str, Any]]
    colony_pressure: dict[str, Any]
    production_ledger: dict[str, Any]
    path_authority: dict[str, Any]
    local_map_state: dict[str, Any]
    military: dict[str, Any]
    systems: dict[str, Any]
    stores: list[dict[str, Any]]
    settlement_state: dict[str, Any]
    recent_event_log: list[dict[str, Any]]
```

## 5. Public API
- `SaveSystem.save_game(session, slot_name, player_name=...)`
  - Postconditions: writes schema `3.0` save data.
- `CampaignRuntime.load_campaign(save_id)`
  - Preconditions: save exists and contains canonical campaign root.
  - Exceptions: `FileNotFoundError`, `ValueError`, validation errors.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given a saved campaign slot, when metadata is queried, then `schema_version == "3.0"`.
AC-02 [FR-02]: Given a saved campaign slot, when raw JSON is inspected, then `session_state["campaign_state"]["campaign"]` exists and contains kernel slices.
AC-03 [FR-03]: Given a saved campaign slot, when raw JSON is inspected, then no top-level `kernel_*` roots are present in `session_state`.
AC-04 [FR-04]: Given a v2-style or malformed campaign save, when the runtime loads it, then load fails with validation error.
AC-05 [FR-05]: Given an invalid campaign root, when validation runs, then structured debug logging records the failure.

## 7. Performance Requirements
- Save validation must complete within 50 ms for local campaign saves.

## 8. Error Handling
- Missing campaign root raises `ValueError`.
- Invalid kernel world/game state payloads propagate validation exceptions.
- Old saves are unsupported by design and must not be auto-migrated.

## 9. Integration Points
- `frp-backend/engine/save/save_models.py`
- `frp-backend/engine/api/save/session_state.py`
- `frp-backend/engine/api/save/repository.py`
- `frp-backend/engine/api/campaign/persistence.py`
- `frp-backend/engine/api/campaign/runtime.py`

## 10. Test Coverage Target
- 100% coverage on new v3 validation branches.
- Explicit round-trip tests for save, load, and invalid payload rejection.

## Changelog
- 2026-04-03: Introduced schema v3 single-root campaign persistence contract.
