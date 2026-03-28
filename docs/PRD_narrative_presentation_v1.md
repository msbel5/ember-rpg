# PRD: Narrative Presentation v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Narrative Presentation` from `2` to `4` in the first pass by cleaning technical leakage, improving voice, and making onboarding plus command feedback feel more like a role-playing game and less like a state logger.

## 2. Scope
- In scope: title and wizard copy, gameplay narrative formatting, system-message differentiation, and backend-facing narrative cleanup where required.
- Out of scope: full dialog trees, LLM-driven prose generation, or large story-content expansion.

## 3. Functional Requirements
FR-01: Player-facing text SHALL not leak debug or technical scaffolding.
FR-02: Title, wizard, and gameplay surfaces SHALL use copy that suggests stakes, identity, and immediate curiosity.
FR-03: System text, command echoes, and narrative text SHALL remain visually distinct.
FR-04: The first-pass text SHALL favor consequence, actor, and place over bare mechanical reporting.

## 4. Data Structures
```python
class NarrativeLine(TypedDict):
    kind: str
    text: str
    source: str
```

## 5. Public API
No breaking route change.
Internal surfaces MAY normalize or rewrite player-facing narrative strings before rendering, and backend runtime text MAY be adjusted where client cleanup is insufficient.

## 6. Acceptance Criteria
AC-01 [FR-01]: Fresh gameplay screenshots and logs contain no raw debug bracket leaks.
AC-02 [FR-02]: The title and creation flow sound like an RPG invitation rather than a generic form.
AC-03 [FR-03]: Narrative panel formatting distinguishes command history, system alerts, and story text.
AC-04 [FR-04]: Common exploration commands such as `look around` produce more specific and evocative output than bare movement bookkeeping.

## 7. Performance Requirements
- Narrative cleanup SHALL not add a visible delay to normal command presentation.

## 8. Error Handling
- If a richer narrative string is unavailable, the fallback remains clear and readable.
- Cleanup layers SHALL never erase essential gameplay information such as AP loss, danger, or save errors.

## 9. Integration Points
- `frp-backend/engine/api/campaign_runtime.py`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/narrative_panel.gd`
- `frp-backend/tests/test_campaign_api_v2.py`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Add or extend backend tests for player-facing narrative cleanup and Godot tests for narrative formatting or visual separation.

## Changelog
- 2026-03-28: Initial Director Mode narrative-presentation recovery PRD.
