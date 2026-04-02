# PRD: Ember RPG Godot 4.x Client
**Project:** Ember RPG
**Phase:** 4
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Approved

---

## 1. Purpose
Define the shipped Godot client for Ember RPG as a Godot-first, campaign-first frontend over the canonical kernel runtime. The client is responsible for title flow, campaign creation, campaign hydration, world interaction, panel presentation, and save/load UX using the backend's canonical slices only. Terminal play, legacy save discovery, and long chaos runs are not part of the active client contract.

## 2. Scope
- In scope: title menu, multi-step creation shell, adapter selection, campaign gameplay shell, save/load UI, character sheet, settlement panel, inventory and quest panels, world interaction, combat and system consequence presentation, and deterministic screenshot-proof support.
- Out of scope: terminal gameplay, legacy session creation, client-side rules authority, client-side world generation authority, multiplayer, and long-form chaos proof as a release gate.

## 3. Functional Requirements
FR-01: The client SHALL start and continue campaigns exclusively through the campaign route family and canonical save discovery.

FR-02: The client SHALL treat `campaign.world_state`, `campaign.game_state`, `campaign.actors`, `campaign.jobs`, `campaign.reactions`, `campaign.worksites`, `campaign.colony_pressure`, `campaign.production_ledger`, `campaign.stores`, and `campaign.systems` as the authoritative gameplay payload.

FR-03: The title flow SHALL expose a full-shell creation workspace and a canonical continue browser without relying on legacy terminal or compatibility payloads.

FR-04: The gameplay shell SHALL render terrain, entities, and panel state from normalized canonical payloads and SHALL NOT invent gameplay outcomes locally.

FR-05: The client SHALL support both `fantasy_ember` and `scifi_frontier` through one shared scene flow with adapter-driven labels, copy, and theming.

FR-06: The gameplay shell SHALL expose narrative, status, character, settlement, inventory, quest, minimap/world, combat, and save/load surfaces.

FR-07: Every visible object or entry that implies interaction SHALL be actionable or clearly marked inert.

FR-08: UI-initiated commands SHALL resolve through `POST /game/campaigns/{campaign_id}/commands`.

FR-09: The client SHALL preserve backend-authoritative position, location, resources, injury/effect state, colony pressure, store state, and system state without local prediction.

FR-10: Missing assets or partial backend responses SHALL degrade into visible placeholders or explicit error states instead of blank or silent failure.

FR-11: The primary desktop layout SHALL target `1600x900` as the baseline viewport. `1280x720` remains a degraded fallback, not the primary design target.

FR-12: The client SHALL remain operable with keyboard-first navigation across title, creation, continue, gameplay shell, and save/load surfaces.

## 4. Canonical Payload Contract
```python
class CampaignPayload(TypedDict):
    campaign_id: str
    adapter_id: str
    profile_id: str
    narrative: str
    world_state: dict[str, object]
    game_state: dict[str, object]
    actors: list[dict[str, object]]
    jobs: list[dict[str, object]]
    reactions: list[dict[str, object]]
    worksites: list[dict[str, object]]
    colony_pressure: dict[str, object]
    production_ledger: dict[str, object]
    stores: dict[str, object]
    systems: dict[str, object]
```

## 5. Public API
`godot-client/autoloads/backend.gd` SHALL expose:
- `start_campaign_creation(...)`
- `answer_campaign_creation(...)`
- `reroll_campaign_creation(...)`
- `save_campaign_creation_roll(...)`
- `swap_campaign_creation_roll(...)`
- `finalize_campaign_creation(...)`
- `get_campaign(...)`
- `get_campaign_region(...)`
- `get_campaign_settlement(...)`
- `submit_campaign_command(...)`
- `save_campaign(...)`
- `list_campaign_saves(...)`
- `load_campaign(...)`
- `list_saves(...)`

`godot-client/autoloads/game_state.gd` SHALL own normalized `world_state`, `campaign_game_state`, `actors`, `jobs`, `reactions`, `worksites`, `colony_pressure`, `production_ledger`, `stores`, `systems`, and view-model projections derived from those slices.

## 6. Acceptance Criteria
AC-01 [FR-01]: The title flow starts and resumes campaigns without touching legacy session creation routes.

AC-02 [FR-02]: After finalize or load, the gameplay shell is hydrated from canonical payload slices rather than the summary-only `campaign.world` projection.

AC-03 [FR-03]: The title scene exposes a full-shell creation workspace and a continue browser that lists canonical campaign saves only.

AC-04 [FR-04]: Terrain, entities, and shell panels render from normalized canonical state and survive command-driven refresh without authority drift.

AC-05 [FR-05]: Both adapters are playable through the same Godot flow and produce distinct labels and visual treatment without branching the scene graph.

AC-06 [FR-06]: Narrative, status, character, settlement, inventory, quest, minimap/world, combat, and save/load surfaces remain visible and update from canonical state.

AC-07 [FR-07]: Interactable objects, entries, and controls are either actionable or visibly labeled as unavailable/inert.

AC-08 [FR-08]: UI-driven actions and typed commands route through the campaign command endpoint.

AC-09 [FR-09]: Location, resources, effects, colony pressure, stores, and system consequences stay aligned with backend-authoritative values after movement, combat, settlement ticks, and save/load.

AC-10 [FR-10]: Missing assets or partial responses produce visible placeholder/error states instead of crashes or blank panels.

AC-11 [FR-11]: The default Godot viewport and shell layout are tuned for `1600x900`, with `1280x720` remaining usable but clearly a fallback.

AC-12 [FR-12]: Title, creation, continue, gameplay shell, and save/load can all be navigated with keyboard-first automation paths.

## 7. Performance Requirements
- Standard command feedback should be visible within 1 second after the backend response.
- Asset fallback should not block the first playable frame.
- Panel refresh after canonical payload updates should complete without visible shell hitching on standard desktop hardware.

## 8. Error Handling
- Creation and save/load failures keep the current scene operable and show a visible status/error message.
- Partial payload failures preserve the last valid client state where possible.
- Unsupported or missing save entries are reported as unsupported instead of being silently hidden behind compatibility logic.

## 9. Integration Points
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/game_session.gd`
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scripts/net/response_normalizer.gd`
- `godot-client/scripts/ui/*`
- `godot-client/scripts/world/*`
- `docs/prd/active/PRD_save_load.md`
- `docs/prd/active/PRD_creation_surface_v2.md`
- `docs/prd/active/PRD_godot_ux_accessibility_v1.md`

## 10. Test Coverage Target
- Headless tests must cover creation route shapes, title/continue state transitions, canonical payload normalization, panel hydration, and command routing.
- Automation proof must cover title, continue, creation, save/load, world interaction, first command, panel hydration, dialog interaction, map travel, and a bounded combat action through deterministic semantic scenarios.
- Long `100`/`500` turn chaos evidence is a soak lane and is not part of the default release gate.

## Changelog
- 2026-04-01: Rewritten as a Godot-only canonical client contract with `1600x900` baseline, canonical campaign slices, and bounded deterministic automation replacing long-chaos release gating.
- 2026-04-02: Clarified that dialog, travel, and combat verticals are part of the required bounded semantic proof pack.
