# PRD: Ember RPG Godot 4.x Client
**Project:** Ember RPG
**Status:** Active implementation
**Date:** 2026-03-27
**Target Engine:** Godot 4.6.x
**Primary Platforms:** Windows desktop first, Web export second

---

## 1. Purpose
Build the shipable Godot frontend for Ember RPG. The client must deliver a RimWorld-style 16x16 top-down play experience, but it also has to support the full character-creation flow the backend already exposes: questionnaire, stat rolling, save/swap, recommendations, and final confirmation. The client is not a rules engine; it is the interactive presentation and input layer for the campaign backend.

## 2. Scope
- In scope: title flow, campaign creation wizard, world rendering, entity rendering, selectable UI, character sheet, settlement panel, save/load, and adapter selection.
- Out of scope: client-side combat authority, pathfinding authority, procedural generation authority, multiplayer, and runtime Python generation on Web.

## 3. Functional Requirements
FR-01: The client SHALL start from a playable title screen that can create or load a campaign without manual backend setup beyond base URL configuration.
FR-02: The title flow SHALL include guided character creation with questionnaire, current roll, saved roll, reroll, swap-roll, recommended class/alignment/skills, and finalize.
FR-03: The client SHALL support both `fantasy_ember` and `scifi_frontier` as first-class demo blockers.
FR-04: The gameplay scene SHALL render terrain through `TileMapLayer` and entities through `Sprite2D` nodes.
FR-05: The client SHALL expose narrative, status, inventory, minimap, quest, settlement, and character-sheet surfaces.
FR-06: Every visible gameplay object that implies interaction SHALL be selectable or clearly marked as non-interactive.
FR-07: The client SHALL route all gameplay actions through the campaign backend surface used by the terminal client.
FR-08: Camera follow and wheel zoom SHALL remain pixel-stable and authoritative to the backend player position.
FR-09: Placeholder art SHALL remain playable when generated assets are missing.
FR-10: UI and scene transitions SHALL not crash when backend responses are missing, delayed, or partial.

## 4. Data Structures
```python
class CampaignCreationState(TypedDict):
    creation_id: str
    player_name: str
    adapter_id: str
    profile_id: str
    questions: list[dict]
    answers: list[dict]
    class_weights: dict[str, int]
    skill_weights: dict[str, int]
    alignment_axes: dict[str, int]
    recommended_class: str
    recommended_alignment: str
    recommended_skills: list[str]
    current_roll: list[int]
    saved_roll: list[int] | None

class CharacterSheetSnapshot(TypedDict):
    player_name: str
    player_class: str
    alignment: str
    stats: dict[str, int]
    stat_modifiers: dict[str, int]
    skill_proficiencies: list[str]
    hp: int
    max_hp: int
    ap: dict[str, int]
    sp: dict[str, int]
    settlement_role: str | None
    creation_summary: dict[str, object]
```

## 5. Public API
`godot-client/autoloads/backend.gd` SHALL expose:
- `start_creation(player_name, callback, location="")`
- `answer_creation(creation_id, question_id, answer_id, callback)`
- `reroll_creation(creation_id, callback)`
- `save_creation_roll(creation_id, callback)`
- `swap_creation_roll(creation_id, callback)`
- `finalize_creation(creation_id, payload, callback)`
- `create_campaign(...)` only as a test/dev convenience path, not the default title flow

`godot-client/autoloads/game_state.gd` SHALL store normalized campaign, creation, map, settlement, inventory, and narrative state and emit rendering-friendly signals. It SHALL not predict state or invent gameplay outcomes locally.

## 6. Acceptance Criteria
AC-01 [FR-01]: Starting the game opens the title flow and allows either new creation or loading a prior campaign.
AC-02 [FR-02]: The creation wizard displays questions and supports reroll/save/swap before finalize.
AC-03 [FR-03]: Both adapters can be selected from the title flow and produce distinct visual/campaign labels.
AC-04 [FR-04]: Terrain and entities render from backend payloads in the active gameplay scene.
AC-05 [FR-05]: Narrative, status, inventory, minimap, quest, settlement, and character-sheet surfaces are visible and update from state.
AC-06 [FR-06]: Clickable items, NPCs, doors, furniture, and settlement directives can be selected or clearly identified as non-interactive.
AC-07 [FR-07]: A submitted action updates the campaign state through the backend path used by terminal play.
AC-08 [FR-08]: Player follow and zoom remain centered on authoritative position updates.
AC-09 [FR-09]: Placeholder assets still allow a complete playable loop.
AC-10 [FR-10]: Missing or delayed backend responses surface a UI error state instead of crashing the scene.

## 7. Performance Requirements
- Startup and title interaction should remain responsive on Windows desktop hardware.
- Command feedback for standard actions should be visible in under 1 second after backend response.
- Asset fallback should not block the first playable frame.

## 8. Error Handling
- If a creation or campaign response is missing, keep the current scene alive and surface a visible error.
- If generated assets cannot be loaded, fall back to bundled or placeholder assets.
- If backend routing differs by environment, the backend facade owns normalization instead of scene scripts.

## 9. Integration Points
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scripts/world/*`
- `godot-client/scripts/ui/*`
- `godot-client/scripts/asset/asset_bootstrap.gd`

## 10. Test Coverage Target
- Headless tests must cover creation route shapes, state normalization, scene instantiation, and asset fallback.
- Visual QA must cover title creation, gameplay entry, selectable objects, and save/load.

## 11. Visual Direction
- 16x16 pixel top-down presentation.
- RimWorld-style readability with strong panel hierarchy and a clear command surface.
- Every important object should read as either interactive or intentionally inert.

## 12. Changelog
- 2026-03-27: Rewritten to align the client PRD with campaign-first onboarding, character creation, selectable gameplay surfaces, and adapter-blocking demo requirements.
