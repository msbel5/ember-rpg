# PRD: Creation Surface V2
**Project:** Ember RPG  
**Phase:** 0  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-31  
**Status:** Approved  

---

## 1. Purpose
Creation Surface V2 defines the authoritative player-facing campaign creation flow for Ember RPG. Its goal is to unblock entry into the game, replace the fragile modal wizard feel with a readable creation workspace, and ensure the player can shape world premise, commander identity, colony pressure, and starting deterministic conditions before the campaign begins.

## 2. Scope
- In scope: title-screen creation layout, grouped questionnaire rendering, live genesis preview, rolled-pool assignment UX, save/swap roll state visibility, dossier summary, keyboard and mouse accessibility, 1280x720 and 2K layout behavior, screenshot capture proof points.
- Out of scope: deep visual polish for the rest of gameplay, final art direction, LLM-assisted onboarding, non-campaign legacy save flows, macro-world gameplay itself.

## 3. Functional Requirements (FR)
FR-01: The creation surface must render as a full-shell workspace, not a small modal panel centered in unused screen space.

FR-02: The creation surface must expose the creation flow in deterministic phases:
1. Identity
2. Questionnaire
3. Rolled Pool
4. Allocation and Build
5. Dossier

FR-03: The identity phase must allow keyboard and mouse completion of player name, adapter, optional profile, and optional seed.

FR-04: The questionnaire phase must render all available question groups and questions on one scrollable surface, with no one-question-at-a-time dropdown flow.

FR-05: The questionnaire phase must display a live campaign genesis preview that updates whenever visible answers change.

FR-06: The rolled-pool phase must clearly distinguish:
- active rolled pool
- saved rolled pool
- reroll action
- lock/save action
- swap action

FR-07: The build phase must forbid freeform stat allocation and instead enforce a rules-driven assignment model based on the current active rolled array.

FR-08: The build phase must make assignment legality obvious through visible controls and explanatory copy.

FR-09: The dossier phase must present a readable campaign summary including:
- world premise
- commander profile
- starting pressure
- quest seed themes
- recommended frame
- final build

FR-10: Returning from dossier to build must preserve manual build edits.

FR-11: The creation surface must support keyboard-first advancement without hidden focus traps.

FR-12: The creation surface must provide screenshot-proof capture through existing F12 / viewport capture flow.

## 4. Data Structures
```python
class CreationStep(Enum):
    IDENTITY = 0
    QUESTIONNAIRE = 1
    ROLL = 2
    BUILD = 3
    SUMMARY = 4


@dataclass
class CreationQuestionOption:
    id: str
    text: str
    facet_weights: dict[str, int]
    adapter_weights: dict[str, int]
    faction_bias: dict[str, int]
    settlement_bias: dict[str, int]
    world_tags: list[str]
    tone_tags: list[str]
    quest_themes: list[str]


@dataclass
class CreationQuestion:
    id: str
    text: str
    answers: list[CreationQuestionOption]
    selected_answer_id: str | None = None


@dataclass
class CreationQuestionGroup:
    id: str
    title: str
    subtitle: str
    questions: list[CreationQuestion]


@dataclass
class AllocationRules:
    mode: Literal["rolled_array_assignment"]
    strict_permutation: bool
    ability_order: list[str]


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
```
- Preconditions: TitleScreen scene is instantiated.
- Postconditions: Character creation content is reflowed into a readable shell with form and preview panes.
- Exceptions raised: none; must fail soft and keep scene operable.

```python
func _update_creation_preview_panel() -> void
```
- Preconditions: Creation payload may be partial.
- Postconditions: Preview copy reflects the current step and available deterministic state.

```python
func _refresh_creation_view() -> void
```
- Preconditions: `wizard_step` is valid.
- Postconditions: Exactly one creation phase is visible, focus is restored to the primary control, preview is synchronized.

### Backend Campaign Creation Payload
```python
CampaignCreationStateResponse
```
- Must include:
  - `question_groups`
  - `facet_scores`
  - `campaign_genesis`
  - `world_seed_hints`
  - `allocation_rules`
  - `roll_pool`
  - `saved_roll_pool`

### Finalize Request
```python
CampaignCreationFinalizeRequest
```
- Must accept:
  - `assigned_stats`
  - `selected_facets`
  - `creation_profile`

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given a 1280x720 viewport, when the player opens New Game, then the creation shell occupies the majority of the screen and no longer appears as a narrow centered dialog.

AC-02 [FR-02]: Given the creation shell is open, when the player advances between phases, then the phase label and visible surface change consistently across all five phases.

AC-03 [FR-03]: Given focus is in the identity phase, when the player enters a name and activates the primary action, then creation starts without requiring pixel-perfect mouse targeting.

AC-04 [FR-04]: Given questionnaire data contains multiple groups and questions, when the questionnaire phase opens, then all questions are visible within one scrollable surface.

AC-05 [FR-05]: Given the player changes questionnaire selections, when the answer changes, then the live genesis preview text changes in the same frame.

AC-06 [FR-06]: Given a creation state with current and saved rolls, when the rolled-pool phase opens, then the UI labels clearly identify active and saved pools.

AC-07 [FR-07]: Given the build phase is active, when the player inspects stat controls, then freeform numeric entry is unavailable and only legal permutation-preserving operations are enabled.

AC-08 [FR-08]: Given the build phase is active, when the player hovers or reads the allocation area, then the rule "assigned stats remain a permutation of the active rolled array" is visible.

AC-09 [FR-09]: Given the dossier phase is active, when the summary renders, then it includes world premise, commander profile, colony pressure, quest seeds, recommended frame, and final build.

AC-10 [FR-10]: Given the player edits class, alignment, skills, and assigned stats, when they move to dossier and back, then those edits remain intact.

AC-11 [FR-11]: Given the creation shell is open, when the player uses keyboard navigation only, then each phase has a sane primary focus target and Enter/Space trigger the correct primary action.

AC-12 [FR-12]: Given the creation shell is visible, when the player triggers viewport capture, then the screenshot pipeline emits a title/creation proof artifact without requiring OS-level capture.

## 7. Performance Requirements
- Title surface phase transitions must complete within 1 frame in headless tests.
- Preview refresh must complete within 16 ms on a typical desktop scene tree.
- No creation step may allocate or rebuild enough controls to visibly hitch on ordinary questionnaire sizes (< 20 questions).

## 8. Error Handling
- Empty player name blocks creation start with explicit status text.
- Missing questionnaire answers block progression to the rolled-pool phase with explicit status text.
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
- `frp-backend/engine/api/campaign_runtime.py`

## 10. Test Coverage Target
- Minimum coverage target for changed backend creation behavior: 95%.
- Minimum coverage target for title-screen flow touched in headless tests: all AC branches above must have direct assertions.

## Changelog
- 2026-04-01: Promoted to approved after title-shell headless coverage and headless automation scenario proof (`title_creation_bridge`) validated the current creation workspace contract.
