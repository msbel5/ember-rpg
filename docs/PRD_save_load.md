# PRD: Save/Load System
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Approved  

---

## 1. Purpose
Define the campaign-first persistence contract for Ember RPG. Save/load must preserve the active campaign, support in-session quick save and explicit slot restore, and expose enough metadata for terminal and Godot resume flows. The backend contract is implemented; final demo closure still requires the Godot title flow to graduate from cached-slot `Continue` to a true save browser, which is tracked in QA rather than by changing the wire format.

## 2. Scope
- In scope: campaign save routes, player-scoped save discovery, slot metadata, save/load UI contracts for terminal and Godot, and compatibility notes for legacy session routes.
- Out of scope: cloud sync, multiplayer save coordination, encrypted saves, and screenshot thumbnails embedded in slot metadata.

## 3. Functional Requirements
FR-01: The active player-facing save path SHALL use the campaign-first route family under `/game/campaigns/...`.
FR-02: The save payload SHALL preserve campaign state, realized region state, settlement state, recent event log, character sheet inputs, and enough session state to resume in a playable scene.
FR-03: The system SHALL support explicit named saves through backend routes and through terminal and Godot UI actions.
FR-04: The system SHALL expose campaign-scoped save listing for in-session save/load panels.
FR-05: The system SHALL expose player-scoped save discovery through `GET /game/saves/{player_id}` for title/resume flows and terminal load discovery.
FR-06: Loading a missing or corrupt save SHALL return a clear user-facing error without crashing the current client scene or terminal loop.
FR-07: Loading a campaign save SHALL restore the active runtime as a playable campaign, not a legacy blank shell.
FR-08: The contract SHALL preserve `last_save_slot` and slot metadata so clients can seed default quick-save and continue behavior.
FR-09: Legacy session save routes MAY remain available as compatibility scaffolding, but they SHALL NOT be the primary player-facing contract.

## 4. Data Structures
```python
class CampaignSaveRequest(TypedDict):
    player_id: str | None
    slot_name: str | None


class CampaignSaveSummary(TypedDict):
    save_id: str
    slot_name: str
    player_id: str
    timestamp: str
    schema_version: str
    location: str | None
    game_time: str | None


class CampaignSaveResponse(TypedDict):
    save_id: str
    slot_name: str
    timestamp: str
    schema_version: str


class PersistedCampaignState(TypedDict):
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int
    active_region_id: str
    world_snapshot: dict[str, object]
    settlement_state: dict[str, object]
    recent_event_log: list[dict[str, object]]
```

## 5. Public API
- `POST /game/campaigns/{campaign_id}/save`
  - Preconditions: `campaign_id` exists; optional `slot_name` and `player_id` may be supplied.
  - Postconditions: returns `CampaignSaveResponse` with canonical `save_id == slot_name`.
  - Errors: `404` if the campaign is missing.
- `GET /game/campaigns/{campaign_id}/saves`
  - Preconditions: `campaign_id` exists.
  - Postconditions: returns `list[CampaignSaveSummary]` for the active campaign context.
  - Errors: `404` if the campaign is missing.
- `POST /game/campaigns/load/{save_id}`
  - Preconditions: `save_id` refers to a readable campaign save.
  - Postconditions: returns a playable `CampaignSnapshotResponse`.
  - Errors: `404` for missing saves, `422` for corrupt or invalid save payloads.
- `GET /game/saves/{player_id}`
  - Preconditions: `player_id` is a player-scoped lookup key, usually the player name.
  - Postconditions: returns save discovery metadata for title/resume flows and terminal load lists.
- Compatibility routes still present in the codebase:
  - `POST /game/session/{session_id}/save`
  - `POST /game/session/load/{save_id}`
  - These routes are not the primary player-facing contract.

## 6. Acceptance Criteria
AC-01 [FR-01]: In-session save/load in Godot and terminal use `/game/campaigns/{campaign_id}/save`, `/game/campaigns/{campaign_id}/saves`, and `/game/campaigns/load/{save_id}` as the active runtime path.
AC-02 [FR-02]: Saving and loading preserves active region, settlement state, recent event log, character creation metadata, and playable location.
AC-03 [FR-03]: A named save can be created manually from both clients without advancing the world tick.
AC-04 [FR-04]: The gameplay shell can list campaign saves and restore the selected slot.
AC-05 [FR-05]: Title/resume and terminal load discovery can obtain save metadata from `GET /game/saves/{player_id}`.
AC-06 [FR-06]: Missing or corrupt saves surface a clear error and do not crash the scene or terminal loop.
AC-07 [FR-07]: Loading a campaign save returns the player to a playable campaign scene with narrative, map, and settlement state intact.
AC-08 [FR-08]: `last_save_slot` is preserved so quick-save defaults and cached continue behavior can be restored.
AC-09 [FR-09]: Legacy session save routes remain compatibility-only and are not documented as the primary user path.

## 7. Performance Requirements
- Manual save and load should complete in under 250 ms for the typical demo campaign on local hardware, excluding client rendering time.
- Listing saves should remain fast enough for title or in-session panels to populate without noticeable delay.

## 8. Error Handling
- Invalid or missing `slot_name` falls back to backend defaults rather than crashing the request.
- Missing saves return a clear not-found error.
- Corrupt saves return a validation-style error rather than silently spawning a new campaign.
- Clients must keep the current playable state on load failure and surface the failure inline.

## 9. Integration Points
- `frp-backend/engine/api/campaign_routes.py`
- `frp-backend/engine/api/campaign_runtime.py`
- `frp-backend/engine/api/save_routes.py`
- `frp-backend/engine/api/save_system.py`
- `frp-backend/tools/campaign_client.py`
- `frp-backend/tools/play.py`
- `frp-backend/tools/play_topdown.py`
- `godot-client/autoloads/backend.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scenes/title_screen.gd`

## 10. Test Coverage Target
- Targeted backend coverage must include campaign save, campaign load, campaign save listing, player-scoped save discovery, invalid save handling, and character metadata round-trip.
- Terminal-targeted coverage must include startup `New / Load / Quit`, load discovery, invalid input handling, and post-load narrative reset.
- Godot headless coverage must include campaign save/load request shapes and default save-slot behavior.

## Changelog
- 2026-03-28: Rewritten to make campaign-first save/load authoritative, align slot metadata with the live campaign routes, and move remaining title resume gaps into QA tracking.
