# PRD: Save/Load System
**Project:** Ember RPG
**Phase:** 4
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Approved

---

## 1. Purpose
Define the Godot-first persistence contract for Ember RPG. Save/load must preserve the active campaign, restore a playable Godot session without reconstruction drift, and persist the canonical kernel runtime roots as the only authoritative gameplay source.

## 2. Scope
- In scope: campaign save routes, player-scoped save discovery for the Godot title flow, in-session quick save, explicit slot restore, canonical kernel payload validation, and Godot-facing slot metadata.
- Out of scope: terminal save UX, legacy session compatibility, cloud sync, multiplayer coordination, encrypted saves, and screenshot thumbnails embedded in save metadata.

## 3. Functional Requirements
FR-01: The active player-facing save path SHALL use the campaign-first route family under `/game/campaigns/...`.
FR-02: The save payload SHALL preserve campaign state, realized region state, settlement state, recent event log, creation metadata, canonical `kernel_world_state`, canonical `kernel_game_state`, canonical actors, jobs, reactions, worksites, stores, and systems slices.
FR-03: The system SHALL support explicit named saves through backend routes and through Godot UI actions.
FR-04: The system SHALL expose campaign-scoped save listing for in-session save/load panels.
FR-05: The system SHALL expose player-scoped save discovery through `GET /game/saves/{player_id}` for the Godot title and continue flows.
FR-06: Loading a missing or corrupt save SHALL return a clear user-facing error without crashing the active Godot scene.
FR-07: Loading a campaign save SHALL restore the active runtime as a playable campaign, not a reconstructed compatibility shell.
FR-08: The contract SHALL preserve `last_save_slot` and slot metadata so quick-save defaults and cached continue behavior can be restored.
FR-09: Invalid or incomplete canonical kernel roots SHALL fail fast during strict load; the runtime SHALL NOT silently rebuild gameplay authority from legacy shims.
FR-10: Deprecated terminal and legacy session save routes MAY remain in the codebase temporarily, but they SHALL NOT be part of the active product contract or release signoff.

## 4. Data Structures
```python
class CampaignSaveSummary(TypedDict):
    save_id: str
    slot_name: str
    player_id: str
    timestamp: str
    schema_version: str
    location: str | None
    game_time: str | None
    adapter_id: str


class PersistedCampaignState(TypedDict):
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int
    active_region_id: str
    world_snapshot: dict[str, object]
    kernel_world_state: dict[str, object]
    kernel_game_state: dict[str, object]
    kernel_actors: list[dict[str, object]]
    kernel_jobs: list[dict[str, object]]
    kernel_reactions: list[dict[str, object]]
    kernel_worksites: list[dict[str, object]]
    kernel_stores: list[dict[str, object]]
    kernel_systems: dict[str, object]
    settlement_state: dict[str, object]
    recent_event_log: list[dict[str, object]]
    last_save_slot: str | None
```

## 5. Public API
- `POST /game/campaigns/{campaign_id}/save`
  - Preconditions: `campaign_id` exists; optional `slot_name` and `player_id` may be supplied.
  - Postconditions: persists the canonical campaign runtime and returns `save_id`, `slot_name`, `timestamp`, and `schema_version`.
  - Errors: `404` if the campaign is missing.
- `GET /game/campaigns/{campaign_id}/saves`
  - Preconditions: `campaign_id` exists.
  - Postconditions: returns `list[CampaignSaveSummary]` for the active campaign context.
  - Errors: `404` if the campaign is missing.
- `POST /game/campaigns/load/{save_id}`
  - Preconditions: `save_id` refers to a readable campaign save.
  - Postconditions: returns a playable `CampaignSnapshotResponse`.
  - Errors: `404` for missing saves, `422` for corrupt or invalid canonical payloads.
- `GET /game/saves/{player_id}`
  - Preconditions: `player_id` is a player-scoped lookup key used by the title/continue surface.
  - Postconditions: returns save discovery metadata for supported Godot flows only.

## 6. Runtime Authority
Campaign save/load is authoritative only when rooted in canonical kernel slices. The live runtime SHALL persist and restore:
1. `campaign.world_state`
2. `campaign.game_state`
3. `campaign.actors`
4. `campaign.jobs`
5. `campaign.reactions`
6. `campaign.worksites`
7. `campaign.colony_pressure`
8. `campaign.production_ledger`
9. `campaign.stores`
10. `campaign.systems`

Player-facing Godot flows SHALL treat these canonical slices as the runtime truth. Deprecated terminal or compatibility payloads SHALL NOT be consulted for active gameplay restoration.

## 7. Acceptance Criteria
AC-01 [FR-01]: In-session save/load in Godot uses `/game/campaigns/{campaign_id}/save`, `/game/campaigns/{campaign_id}/saves`, and `/game/campaigns/load/{save_id}` as the active runtime path.
AC-02 [FR-02]: Saving and loading preserves active region, settlement state, recent event log, creation metadata, canonical kernel roots, and playable location.
AC-03 [FR-03]: A named save can be created manually from Godot without advancing the world tick.
AC-04 [FR-04]: The gameplay shell can list campaign saves and restore the selected slot.
AC-05 [FR-05]: The title and continue browser can obtain save metadata from `GET /game/saves/{player_id}`.
AC-06 [FR-06]: Missing or corrupt saves surface a clear error and do not crash the active Godot scene.
AC-07 [FR-07]: Loading a campaign save returns the player to a playable campaign scene with narrative, map, settlement, stores, and systems state intact.
AC-08 [FR-08]: `last_save_slot` is preserved so quick-save defaults and cached continue behavior can be restored.
AC-09 [FR-09]: Given a campaign save contains invalid `kernel_game_state` or `kernel_world_state`, when strict load is requested, then the load fails fast with a validation-style error instead of reconstructing a partial runtime from compatibility shims.
AC-10 [FR-10]: Deprecated terminal or legacy session routes are excluded from active release signoff and are documented only as deprecated code paths.

## 8. Performance Requirements
- Manual save and load should complete in under 250 ms for a typical local campaign, excluding client rendering time.
- Listing saves should remain fast enough for the Godot title and in-session panels to populate without noticeable delay.

## 9. Error Handling
- Invalid or missing `slot_name` falls back to backend defaults rather than crashing the request.
- Missing saves return a clear not-found error.
- Corrupt saves return a validation-style error rather than silently spawning a new campaign.
- Invalid canonical kernel roots return a validation-style error before campaign hydration starts.
- Clients must keep the current playable state on load failure and surface the failure inline.

## 10. Integration Points
- `frp-backend/engine/api/campaign/persistence.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/save/`
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scenes/title_screen.gd`

## 11. Test Coverage Target
- Targeted backend coverage must include campaign save, campaign load, campaign save listing, player-scoped save discovery, invalid save handling, and canonical kernel round-trip.
- Godot headless coverage must include title continue discovery, in-session save/load, default quick-save slot behavior, and canonical slice hydration after load.

## Changelog
- 2026-04-01: Rewritten as a Godot-only canonical persistence contract; removed terminal-first language and made strict canonical kernel validation mandatory.
