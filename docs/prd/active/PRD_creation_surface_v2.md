# PRD: Creation Surface V2
**Project:** Ember RPG
**Phase:** 0
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Approved

---

## 1. Purpose
Creation Surface V2 defines the authoritative player-facing campaign creation flow for Ember RPG. Its goal is to provide a readable, deterministic, full-shell creation workspace that feeds directly into the canonical campaign runtime and remains operable through keyboard and mouse without pixel-perfect interaction.

## 2. Scope
- In scope: title-screen creation layout, grouped questionnaire rendering, live genesis preview, rolled-pool assignment UX, save/swap roll state visibility, dossier summary, keyboard and mouse accessibility, `1600x900` primary layout behavior, `1280x720` fallback behavior, viewport screenshot proof points.
- Out of scope: terminal creation flows, legacy save flows, LLM-assisted onboarding, macro-world gameplay itself, and speculative art-direction polish outside the creation shell.

## 3. Functional Requirements
FR-01: The creation surface SHALL render as a full-shell workspace, not a centered modal consuming a minority of the viewport.

FR-02: The creation surface SHALL expose deterministic phases:
1. Identity
2. Questionnaire
3. Rolled Pool
4. Allocation and Build
5. Dossier

FR-03: The identity phase SHALL allow keyboard and mouse completion of player name, adapter, optional profile, and optional seed.

FR-04: The questionnaire phase SHALL render grouped questions on one scrollable surface instead of one-question-at-a-time modal flow.

FR-05: The questionnaire phase SHALL display a live genesis preview that updates whenever visible answers change.

FR-06: The rolled-pool phase SHALL clearly distinguish active rolled pool, saved rolled pool, reroll, save, and swap actions.

FR-07: The build phase SHALL enforce a rules-driven rolled-array assignment model and SHALL NOT expose unrestricted freeform stat editing.

FR-08: The build phase SHALL make assignment legality obvious through visible controls and explanatory copy.

FR-09: The dossier phase SHALL present world premise, commander profile, starting pressure, quest seed themes, recommended frame, and final build.

FR-10: Returning from dossier to build SHALL preserve manual build edits.

FR-11: The surface SHALL support keyboard-first advancement without hidden focus traps.

FR-12: The creation shell SHALL provide viewport screenshot proof through the Godot capture flow.

FR-13: The creation shell SHALL be tuned for `1600x900` as primary baseline and remain legible at `1280x720` fallback.

## 4. Canonical View Model
```python
class CreationStep(Enum):
    IDENTITY = 0
    QUESTIONNAIRE = 1
    ROLL = 2
    BUILD = 3
    SUMMARY = 4


@dataclass
class CampaignGenesisPreview:
    world_premise: str
    commander_profile: str
    starting_pressure: str
    quest_seed_themes: list[str]
    recommended_adapter: str
```

## 5. Public API
### Godot Title Surface
```python
func _install_creation_shell() -> void
func _update_creation_preview_panel() -> void
func _refresh_creation_view() -> void
```

### Backend Campaign Creation Payload
`CampaignCreationStateResponse` SHALL include:
- `question_groups`
- `facet_scores`
- `campaign_genesis`
- `world_seed_hints`
- `allocation_rules`
- `current_roll`
- `saved_roll`

### Finalize Request
`CampaignCreationFinalizeRequest` SHALL accept:
- `assigned_stats`
- `selected_facets`
- `creation_profile`

## 6. Acceptance Criteria
AC-01 [FR-01]: At `1600x900`, the creation shell occupies the majority of the screen and reads as a workspace rather than a modal.

AC-02 [FR-02]: The phase label and visible surface change consistently across all five phases.

AC-03 [FR-03]: Identity fields can be completed and advanced through keyboard-only interaction.

AC-04 [FR-04]: Questionnaire data with multiple groups renders inside one scrollable surface.

AC-05 [FR-05]: Changing questionnaire selections updates the genesis preview in the same frame.

AC-06 [FR-06]: Current and saved rolls are visibly distinguished.

AC-07 [FR-07]: The build phase disables illegal freeform allocation paths and preserves the rolled-array constraint.

AC-08 [FR-08]: The allocation rules are visible in the build surface without requiring external docs.

AC-09 [FR-09]: The dossier summarizes world premise, commander profile, colony pressure, quest seeds, recommended frame, and final build.

AC-10 [FR-10]: Manual build edits persist when moving to dossier and back.

AC-11 [FR-11]: Keyboard navigation has a sane primary focus target at every phase.

AC-12 [FR-12]: The screenshot pipeline emits creation proof artifacts without requiring OS capture.

AC-13 [FR-13]: The layout is optimized for `1600x900` and remains usable at `1280x720` fallback without clipped primary actions.

## 7. Performance Requirements
- Phase transitions should complete within one frame in headless tests.
- Preview refresh should complete within 16 ms on ordinary questionnaire sizes.
- No phase should visibly hitch on normal creation payloads.

## 8. Error Handling
- Empty player name blocks creation start with explicit status text.
- Missing questionnaire answers block progression with explicit status text.
- Failed backend creation requests leave the current phase intact and surface an error message.
- Screenshot capture failure reports a visible status message and does not break input handling.

## 9. Integration Points
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scripts/ui/ember_theme.gd`
- `godot-client/tests/run_headless_tests.gd`
- `godot-client/tests/automation/`
- `frp-backend/engine/core/character_creation.py`
- `frp-backend/engine/api/campaign_models.py`
- `frp-backend/engine/api/campaign/runtime.py`

## 10. Test Coverage Target
- Changed backend creation behavior: targeted AC coverage.
- Headless and automation coverage: all AC branches above must have direct assertions or scenario proof.

## Changelog
- 2026-04-01: Updated to `1600x900` primary layout, Godot-only contract, and bounded automation proof instead of pixel-perfect/manual-first validation.
