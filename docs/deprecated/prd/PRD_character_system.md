# PRD: Character System
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Implemented  

---

## 1. Purpose
Define the canonical character model for Ember RPG across campaign creation, save/load, terminal presentation, and Godot presentation. This document covers the questionnaire-backed creation flow, deterministic roll handling, finalized build metadata, and the shipped `character_sheet` snapshot used by both clients.

## 2. Scope
- In scope: six abilities, modifiers, proficiencies, creation questions and answers, current and saved roll arrays, recommended build metadata, validated stat assignment, and the runtime `character_sheet` payload.
- Out of scope: combat rules, spell resolution, world generation, client-only layout choices, and non-player NPC progression.

## 3. Functional Requirements
FR-01: The character model SHALL support the six abilities `MIG`, `AGI`, `END`, `MND`, `INS`, and `PRE`.
FR-02: Ability modifiers SHALL use the standard `(score - 10) // 2` rule.
FR-03: The creation flow SHALL produce deterministic current-roll and reroll sequences for the same seed.
FR-04: The creation flow SHALL support saving the current roll and swapping current and saved rolls before finalize.
FR-05: Questionnaire answers SHALL drive recommended class, alignment, and skill outputs.
FR-06: Finalize SHALL support both guided recommendations and validated manual overrides for class, alignment, skills, and assigned stats.
FR-07: The runtime `character_sheet` SHALL expose class, alignment, stats, skills, resources, equipment summary, and creation summary in a client-friendly shape.
FR-08: Save/load SHALL preserve creation metadata and the finalized character build without re-rolling or recomputing a different identity.
FR-09: Invalid stat names, impossible assignments, or malformed creation payloads SHALL fail clearly.

## 4. Data Structures
```python
class CreationSnapshot(TypedDict):
    creation_id: str
    player_name: str
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


class CreationSummary(TypedDict):
    recommended_class: str
    recommended_alignment: str
    recommended_skills: list[str]
    selected_skills: list[str]
    answers: list[dict[str, object]]
    class_weights: dict[str, int]
    skill_weights: dict[str, int]
    alignment_axes: dict[str, int]
    stat_source: str
    rolled_values: list[int]
    saved_roll: list[int] | None
```

## 5. Public API
- `roll_stat_array(rng=None) -> list[int]`
  - Preconditions: `rng` may be omitted; if provided it must behave like `random.Random`.
  - Postconditions: returns a six-value rolled array.
- `assign_stats_to_class(scores, class_name) -> dict[str, int]`
  - Preconditions: `scores` must contain six legal values.
  - Postconditions: returns an ability assignment for the chosen class.
  - Errors: raises `ValueError` for malformed score sets or invalid classes.
- `CreationState.answer_question(question_id, answer_id) -> None`
  - Updates class, skill, and alignment weights.
- `CreationState.reroll(rng=None) -> list[int]`
  - Produces the next deterministic roll sequence for the creation seed.
- `CreationState.save_current_roll() -> list[int]`
  - Stores the current roll for later swap.
- `CreationState.swap_rolls() -> dict[str, list[int] | None]`
  - Exchanges current and saved rolls.
  - Errors: raises `ValueError` if no saved roll exists.
- `CreationState.recommended_class() -> str`
- `CreationState.recommended_alignment() -> str`
- `CreationState.recommended_skills(class_name=None) -> list[str]`
- `CampaignRuntime.build_character_sheet(campaign_id) -> CharacterSheetSnapshot`
  - Converts the finalized player and settlement state into the client-friendly sheet payload used by terminal and Godot.

## 6. Acceptance Criteria
AC-01 [FR-01]: A finalized character always exposes the six required abilities in the `character_sheet`.
AC-02 [FR-02]: Ability modifiers match expected values for low, baseline, and high scores.
AC-03 [FR-03]: The same creation seed yields the same first roll and reroll sequence.
AC-04 [FR-04]: Save-roll and swap-roll preserve current and saved arrays correctly.
AC-05 [FR-05]: The same questionnaire answers produce the same recommended class, alignment, and skills.
AC-06 [FR-06]: Finalize accepts recommended defaults or validated user overrides without producing inconsistent stats or skills.
AC-07 [FR-07]: The shipped `character_sheet` contains class, alignment, stats, skills, resources, equipment summary, and creation summary.
AC-08 [FR-08]: Save/load round-trips preserve creation metadata, selected skills, assigned stats, and derived sheet output.
AC-09 [FR-09]: Invalid stat keys, malformed assignments, or malformed creation payloads return a clear validation failure.

## 7. Performance Requirements
- Character-sheet generation should be cheap enough to refresh on normal client update cycles.
- Creation-state updates should be effectively instantaneous relative to network latency.

## 8. Error Handling
- Invalid stat names or malformed assignments must fail explicitly.
- Swapping without a saved roll must fail explicitly.
- Missing optional creation metadata should degrade gracefully in the sheet instead of crashing client rendering.
- Save/load must not silently regenerate a different build if creation metadata is incomplete or stale.

## 9. Integration Points
- `frp-backend/engine/core/character_creation.py`
- `frp-backend/engine/api/campaign_runtime.py`
- `frp-backend/engine/api/campaign_state.py`
- `frp-backend/engine/api/campaign_models.py`
- `frp-backend/tools/campaign_client.py`
- `frp-backend/tools/play.py`
- `frp-backend/tools/play_topdown.py`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`

## 10. Test Coverage Target
- Targeted backend coverage must include deterministic creation seeding, reroll/save/swap behavior, recommended build stability, validation failures, and character-sheet payload shape.
- Terminal and Godot preflight coverage must include character-sheet parity and creation-summary normalization.

## Changelog
- 2026-03-28: Rewritten to match the shipped `character_sheet` payload, deterministic campaign creation flow, and save/load persistence expectations.
