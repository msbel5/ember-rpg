# PRD: Character System
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-27
**Status:** Authoritative

---

## 1. Purpose
Define the canonical character model for Ember RPG. This module covers the six-stat build, skills, alignment, class recommendations, rolled stat arrays, and the character-sheet snapshot used by both terminal and Godot onboarding.

## 2. Scope
- In scope: character identity, six stats, modifiers, skill proficiencies, alignment axes, rolled stat arrays, recommended build metadata, and serialized character-sheet output.
- Out of scope: combat resolution, spell effects, world generation, and client-only UI layout.

## 3. Functional Requirements
FR-01: The character model SHALL support the six stats `MIG`, `AGI`, `END`, `MND`, `INS`, and `PRE`.
FR-02: The model SHALL calculate stat modifiers with the standard `(score - 10) // 2` rule.
FR-03: The model SHALL track class, alignment, and skill proficiencies as first-class character identity.
FR-04: The creation flow SHALL support a questionnaire that produces class, alignment, and skill recommendations.
FR-05: The creation flow SHALL support rolling, saving, and swapping stat arrays before finalize.
FR-06: The character-sheet snapshot SHALL expose stats, modifiers, skills, HP, AP, SP, and creation summary data.
FR-07: The finalized character SHALL persist enough metadata for save/load and UI reconstruction.
FR-08: The module SHALL validate invalid stat names, impossible rolls, and malformed creation payloads.

## 4. Data Structures
```python
@dataclass
class CharacterSheet:
    name: str
    player_class: str
    alignment: str
    stats: dict[str, int]
    stat_modifiers: dict[str, int]
    skill_proficiencies: list[str]
    hp: int
    max_hp: int
    ap: dict[str, int]
    sp: dict[str, int]
    creation_summary: dict[str, object]

@dataclass
class CreationSnapshot:
    creation_id: str
    player_name: str
    questions: list[dict[str, object]]
    answers: list[dict[str, object]]
    current_roll: list[int]
    saved_roll: list[int] | None
    recommended_class: str
    recommended_alignment: str
    recommended_skills: list[str]
```

## 5. Public API
The runtime owns the creation logic already present in `engine.core.character_creation`.
- `roll_stat_array(rng=None) -> list[int]`
- `assign_stats_to_class(scores, class_name) -> dict[str, int]`
- `recommended_alignment_from_axes(axes) -> str`
- `recommended_skills_for_class(state, class_name) -> list[str]`
- `CreationState.answer_question(question_id, answer_id) -> None`
- `CreationState.reroll(rng=None) -> list[int]`
- `CreationState.save_current_roll() -> list[int]`
- `CreationState.swap_rolls() -> dict[str, list[int] | None]`
- `CreationState.recommended_class() -> str`
- `CreationState.recommended_alignment() -> str`
- `CreationState.recommended_skills(class_name=None) -> list[str]`
- `build_character_sheet(...)` in the campaign runtime SHALL convert finalized campaign data into a client-friendly sheet payload.

## 6. Acceptance Criteria
AC-01 [FR-01]: A character sheet can always be constructed with the six required stats.
AC-02 [FR-02]: Stat modifier math matches the standard table for low, mid, and high scores.
AC-03 [FR-03]: Class, alignment, and skill proficiency data appear in the final character-sheet snapshot.
AC-04 [FR-04]: The questionnaire produces a stable recommended class/alignment/skills output for the same answers.
AC-05 [FR-05]: Roll, save, and swap behavior preserves current and saved arrays correctly.
AC-06 [FR-06]: The snapshot includes HP/AP/SP plus a creation summary suitable for UI display.
AC-07 [FR-07]: Finalized characters round-trip through save/load with their creation metadata intact.
AC-08 [FR-08]: Invalid stat keys or malformed creation inputs fail with a clear error.

## 7. Performance Requirements
- Stat and sheet calculations should be trivial and safe to run every frame if needed for UI refresh.
- Creation snapshot generation should be effectively instantaneous relative to backend request latency.

## 8. Error Handling
- Invalid stat names, unknown skill names, or malformed questionnaire answers must raise clear validation errors.
- If no saved roll exists, swap must fail explicitly rather than silently mutating the array.
- If creation metadata is incomplete, the sheet should still render the available fields and mark missing values.

## 9. Integration Points
- `frp-backend/engine/core/character_creation.py`
- `frp-backend/engine/api/campaign_runtime.py`
- `frp-backend/engine/api/campaign_models.py`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/title_screen.gd`
- `frp-backend/tools/play_topdown.py`

## 10. Test Coverage Target
- Every public helper and creation-state mutation must have targeted pytest coverage.
- The creation wizard must have at least one end-to-end test covering questionnaire, reroll, save/swap, and finalize.

## Changelog
- 2026-03-27: Rewritten to make character creation and character-sheet output authoritative for the shipable demo recovery plan.
