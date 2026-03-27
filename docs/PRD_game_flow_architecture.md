# PRD: Game Flow Architecture — Player-Facing Demo Loop
**Project:** Ember RPG
**Phase:** 4
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-27
**Status:** Authoritative

---

## 1. Purpose
Define the player-facing game flow for the shipable demo: title, character creation, campaign start, world reveal, interaction, save/load, and recovery from errors. The flow must feel responsive and readable, not just technically correct.

## 2. Scope
- In scope: onboarding, campaign creation, scene reveal, narrative updates, click and text interactions, selection states, and save/load handoff.
- Out of scope: backend world generation authority, combat rules, pathfinding authority, multiplayer, and streaming architecture that the current demo does not use.

## 3. Functional Requirements
FR-01: The game SHALL begin with a title flow that can create a new campaign or load an existing one.
FR-02: New game SHALL support a guided character creation wizard with questionnaire, roll/save/swap, stat summary, and finalize.
FR-03: The player SHALL enter a readable world scene with narrative, map, and selectable interaction targets.
FR-04: Clicking visible objects SHALL synthesize the same commands that text input can issue.
FR-05: NPCs, items, doors, and settlement directives SHALL surface context actions or clear inert-state labeling.
FR-06: Narrative updates SHALL not hide or replace actionable UI state.
FR-07: Save and load SHALL preserve campaign state without forcing the player back through an empty shell flow.
FR-08: The UI SHALL make it obvious what is selected, what is interactable, and what is currently waiting on backend response.
FR-09: The flow SHALL support both fantasy and sci-fi adapters without separate client code paths.

## 4. Data Structures
```python
class PlayerFlowState(TypedDict):
    mode: str  # title | creation | campaign | save_load | combat
    adapter_id: str
    creation_state: dict[str, object]
    campaign_id: str
    location: str
    selection: dict[str, object] | None
    narrative_log: list[str]
    pending_action: str | None
```

## 5. Public API
The implementation contract is scene-driven rather than service-driven.
- Title and creation scenes must bind to backend creation methods.
- Gameplay scenes must bind to campaign snapshot, region snapshot, settlement snapshot, and command submission.
- Context actions should be emitted as text commands or structured shortcuts through the existing command surface.

## 6. Acceptance Criteria
AC-01 [FR-01]: A new player can reach a campaign without editing config files or restarting the backend.
AC-02 [FR-02]: The creation wizard exposes questionnaire, rolling, save/swap, and finalize controls.
AC-03 [FR-03]: The first campaign scene shows both narrative and at least one clearly selectable interactive object.
AC-04 [FR-04]: Clicking a visible target produces a command-equivalent backend action.
AC-05 [FR-05]: NPC, item, and door interactions either open a context menu or visibly mark the object as inert.
AC-06 [FR-06]: Narrative updates do not clear selection state or hide the command surface.
AC-07 [FR-07]: Save/load restores the player to a playable scene, not a blank shell.
AC-08 [FR-08]: Loading or pending backend work is visible in the UI.
AC-09 [FR-09]: Both adapters use the same flow and only differ in data/labels/assets.

## 7. Performance Requirements
- The first playable scene should appear quickly enough to keep onboarding momentum.
- Click-to-command feedback should be visible immediately at the UI level, even if backend narration takes longer.

## 8. Error Handling
- If a scene payload is incomplete, keep the current scene interactive and show a visible error.
- If a click target disappears before action submission, fall back to command text and clear the selection.
- If save/load fails, preserve the current scene state and show the failure inline.

## 9. Integration Points
- `docs/PRD_godot_client.md`
- `docs/PRD_character_system.md`
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/game_session.tscn`
- `frp-backend/engine/api/campaign_routes.py`
- `frp-backend/engine/api/campaign_runtime.py`

## 10. Test Coverage Target
- Headless tests must cover title flow transitions, selection behavior, and click-to-command synthesis.
- Visual QA must cover creation, scene reveal, object selection, and save/load recovery.

## Changelog
- 2026-03-27: Rewritten to match the shipable demo recovery plan and the new campaign-first onboarding flow.
