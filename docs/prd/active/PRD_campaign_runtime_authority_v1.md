# PRD: Campaign Runtime Authority Cutover
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-04-03  
**Status:** Implemented  

---

## 1. Purpose
Define the single authoritative runtime for Ember RPG. The campaign runtime must own creation, command execution, save/load, and authoritative snapshot delivery. Legacy `/game/session/*` gameplay routes must no longer be mounted in the shipped FastAPI app.

## 2. Scope
- In scope: campaign route authority, command handling, campaign save discovery, campaign save deletion, debug tracing for command entry and snapshot hashes.
- Out of scope: websocket diff transport, migration of old session saves, legacy route compatibility shims.

## 3. Functional Requirements (FR)
FR-01: The FastAPI application must expose campaign-first gameplay routes and must not mount legacy session gameplay routes.
FR-02: The campaign runtime must expose a player-scoped campaign save listing route for the title-shell continue flow.
FR-03: The campaign runtime must expose a campaign save deletion route for the in-game save browser.
FR-04: Every campaign command execution must emit structured debug traces containing command input and pre/post canonical snapshot hashes.

## 4. Data Structures
```python
class CampaignCommandTrace(TypedDict):
    event: str
    campaign_id: str
    command_text: str
    command_type: str
    pre_snapshot_hash: str
    post_snapshot_hash: str
```

## 5. Public API
- `POST /game/campaigns/{campaign_id}/commands`
  - Preconditions: `campaign_id` exists.
  - Postconditions: returns authoritative campaign snapshot.
  - Exceptions: `404` for missing campaign, `422` for invalid command input.
- `GET /game/campaigns/saves/player/{player_id}`
  - Preconditions: `player_id` is non-empty.
  - Postconditions: returns campaign-compatible saves only.
- `DELETE /game/campaigns/saves/{save_id}`
  - Preconditions: `save_id` exists.
  - Postconditions: removes the save file and returns deletion metadata.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given the production FastAPI app, when `/game/session/new` is requested, then the app returns `404`.
AC-02 [FR-02]: Given a player with mixed save files, when `/game/campaigns/saves/player/{player_id}` is requested, then only campaign-compatible saves are returned.
AC-03 [FR-03]: Given an existing campaign save, when `/game/campaigns/saves/{save_id}` is deleted, then subsequent player-scoped save listing excludes that save.
AC-04 [FR-04]: Given a campaign command, when the runtime resolves it, then structured debug logging includes both pre and post snapshot hashes.

## 7. Performance Requirements
- Snapshot hash generation must complete within 25 ms for normal campaign payloads in local development.

## 8. Error Handling
- Missing campaigns return `404`.
- Missing saves return `404`.
- Invalid save IDs or player IDs return `422` when validation fails.

## 9. Integration Points
- `frp-backend/main.py`
- `frp-backend/engine/api/campaign_routes.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/campaign/debug_trace.py`

## 10. Test Coverage Target
- 100% coverage on new campaign route branches.
- Explicit tests for legacy route removal, player-scoped save listing, and save deletion.

## Changelog
- 2026-04-03: Added campaign-only runtime authority requirements and AC-to-pytest mapping.
