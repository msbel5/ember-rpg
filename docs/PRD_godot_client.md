# PRD: Ember RPG Godot 4.x Client
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Approved  

---

## 1. Purpose
Define the shipable Godot frontend for Ember RPG as a campaign-first client. The Godot app is responsible for onboarding, campaign creation, world rendering, selectable gameplay, character and settlement presentation, and save/load UX over the live backend contract. The core campaign runtime already exists; final closure is gated by long-form visual QA and a few remaining interaction-quality gaps tracked in `docs/qa/demo_signoff_matrix.md`.

## 2. Scope
- In scope: title menu, multi-step campaign creation wizard, adapter selection, campaign gameplay shell, save/load UI, character sheet, settlement panel, world clickability, combat and quest panels, and asset fallback behavior.
- Out of scope: client-side rules authority, client-side world generation authority, multiplayer, and runtime Python asset generation on Web.

## 3. Functional Requirements
FR-01: The client SHALL start from a title flow that can begin a new campaign through the campaign creation route family.
FR-02: The title flow SHALL expose the backend-backed questionnaire, stat rolling, save-roll, swap-roll, recommended build summary, manual build edits, and finalize flow.
FR-03: The client SHALL treat `fantasy_ember` and `scifi_frontier` as first-class playable adapters with shared UI flow and data-driven label differences.
FR-04: The gameplay scene SHALL consume campaign snapshots, current region snapshots, and current settlement snapshots from `/game/campaigns/...`.
FR-05: The world view SHALL render terrain through `TileMapLayer` and entities through `Sprite2D` nodes driven by normalized campaign payloads.
FR-06: The shell SHALL expose narrative, status, inventory, minimap, quest, settlement, combat, save/load, and character-sheet surfaces.
FR-07: Every visible object or entry that implies interaction SHALL be selectable, actionable, or clearly marked as inert.
FR-08: The client SHALL route gameplay and commander actions through `POST /game/campaigns/{campaign_id}/commands`.
FR-09: The client SHALL preserve backend-authoritative position, location, AP/SP/HP, and character-sheet values without local gameplay prediction.
FR-10: Missing assets or partial backend responses SHALL degrade into visible placeholder or error states instead of crashing the client.

## 4. Data Structures
```python
class CampaignCreationState(TypedDict):
    creation_id: str
    player_name: str
    adapter_id: str
    profile_id: str
    seed: int
    location: str | None
    questions: list[dict[str, object]]
    answers: list[dict[str, object]]
    class_weights: dict[str, int]
    skill_weights: dict[str, int]
    alignment_axes: dict[str, int]
    recommended_class: str
    recommended_alignment: str
    recommended_skills: list[str]
    current_roll: list[int]
    saved_roll: list[int] | None


class CharacterSheetSnapshot(TypedDict):
    name: str
    race: str
    class_name: str
    level: int
    alignment: str
    stats: list[dict[str, object]]
    skills: list[dict[str, object]]
    resources: dict[str, dict[str, int]]
    armor_class: int
    initiative_bonus: int
    gold: int
    equipment: dict[str, object]
    inventory_count: int
    passives: dict[str, object]
    settlement_role: str
    creation_summary: dict[str, object]


class CampaignSnapshotEnvelope(TypedDict):
    campaign_id: str
    adapter_id: str
    profile_id: str
    narrative: str
    campaign: dict[str, object]
```

## 5. Public API
`godot-client/autoloads/backend.gd` SHALL expose the campaign-first methods below for the active player-facing path:
- `start_campaign_creation(player_name, adapter_id, callback, profile_id="standard", seed=-1, location="")`
- `answer_campaign_creation(creation_id, question_id, answer_id, callback)`
- `reroll_campaign_creation(creation_id, callback)`
- `save_campaign_creation_roll(creation_id, callback)`
- `swap_campaign_creation_roll(creation_id, callback)`
- `finalize_campaign_creation(creation_id, callback, payload={})`
- `get_campaign(campaign_id, callback)`
- `submit_campaign_command(campaign_id, input_text, callback, shortcut="", args={})`
- `get_campaign_region(campaign_id, callback)`
- `get_campaign_settlement(campaign_id, callback)`
- `save_campaign(campaign_id, callback, slot_name="", player_id="")`
- `list_campaign_saves(campaign_id, callback)`
- `load_campaign(save_id, callback)`
- `list_saves(callback, player_id="")` for player-scoped save discovery

`godot-client/autoloads/game_state.gd` SHALL own normalized `creation_state`, `character_sheet`, `map_data`, `world_entities`, `settlement_state`, `recent_event_log`, and `last_save_slot`. Scene scripts SHALL not invent gameplay outcomes locally.

## 6. Acceptance Criteria
AC-01 [FR-01]: The title flow can start a new campaign using the campaign creation route family without using legacy session creation.
AC-02 [FR-02]: The wizard displays questionnaire answers, current and saved rolls, recommended class/alignment/skills, and preserves manual build edits across wizard navigation.
AC-03 [FR-03]: Both adapters are selectable and produce distinct labels, locations, and palette treatment without separate scene code paths.
AC-04 [FR-04]: After finalize or load, the gameplay shell is hydrated from `CampaignSnapshotEnvelope`, current region, and current settlement data.
AC-05 [FR-05]: Terrain and entities render from normalized campaign payloads in the active gameplay scene.
AC-06 [FR-06]: Narrative, status, inventory, minimap, quest, settlement, combat, save/load, and character-sheet surfaces remain visible and update from normalized state.
AC-07 [FR-07]: Clickable world objects, inventory rows, quest rows, settlement directives, and save/load entries either perform a meaningful action or clearly indicate that they are inert.
AC-08 [FR-08]: Typed commands and UI-driven actions resolve through the campaign command route rather than a legacy session action route.
AC-09 [FR-09]: Location and resource displays remain aligned with backend-authoritative values after movement, load, combat, and settlement updates.
AC-10 [FR-10]: Asset fallback and missing backend responses surface a visible placeholder or error state instead of crashing or presenting a blank scene.

## 7. Performance Requirements
- The title flow should remain responsive while stepping through creation and loading saved campaigns on Windows desktop hardware.
- Standard command feedback should be visible within 1 second after the backend response.
- Asset fallback should not block the first playable frame.

## 8. Error Handling
- If a creation request fails, the wizard must stay open and show a visible inline error.
- If a campaign payload is partial, keep the current scene alive and preserve the last valid state where possible.
- If generated art is missing, fall back to bundled or placeholder assets.
- If a save/load operation fails, preserve the current shell state and report the failure to the player without raw stack or backend internals.

## 9. Integration Points
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/game_session.gd`
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scripts/net/response_normalizer.gd`
- `godot-client/scripts/world/*`
- `godot-client/scripts/ui/*`
- `docs/PRD_character_system.md`
- `docs/PRD_save_load.md`
- `docs/qa/demo_signoff_matrix.md`

## 10. Test Coverage Target
- Headless tests must cover creation route shapes, title flow state transitions, save/load request shapes, normalized character-sheet state, and clickable panel routing.
- Visual QA must cover both adapters, creation wizard proof, gameplay proof, save/load proof, and the long-form `100-turn`, `30-minute`, and final chaos matrices tracked in QA.

## Changelog
- 2026-03-28: Rewritten to match the live `/game/campaigns/...` contract, the shipped character-sheet payload, and the remaining Godot demo signoff gates.
