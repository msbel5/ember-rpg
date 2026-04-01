# PRD: UI Polish v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `UI Polish` from `2` to `4` in the first pass by replacing the stock-toolkit look of the title, wizard, and gameplay shell with a coherent authored presentation that still fits the current gameplay layout.

## 2. Scope
- In scope: title composition, wizard readability, gameplay shell spacing and hierarchy, button states, panel styling, and focus affordances.
- Out of scope: fully painted BG2-style UI art or hand-illustrated frames.

## 3. Functional Requirements
FR-01: The title screen SHALL look intentional, not like three default buttons on a dark fill.
FR-02: The creation wizard SHALL read as a real authored onboarding flow with stronger hierarchy and spacing.
FR-03: Gameplay panels SHALL share one visual language for headers, borders, body text, and action buttons.
FR-04: Focus, hover, disabled, and busy states SHALL remain visually distinct.
FR-05: The resulting shell SHALL remain readable at `1280x720`.

## 4. Data Structures
```python
class UiThemeToken(TypedDict):
    font_path: str | None
    panel_bg: str
    panel_border: str
    accent: str
    warning: str
```

## 5. Public API
No external API change.
Internal surfaces MAY introduce shared theme resources or helper methods for applying repeated styles.

## 6. Acceptance Criteria
AC-01 [FR-01]: Fresh title screenshots no longer read as an empty dark screen with default buttons.
AC-02 [FR-02]: The wizard’s step headers, body copy, and primary actions have clear visual priority.
AC-03 [FR-03]: Sidebar, command bar, and overlays feel like one authored interface family.
AC-04 [FR-04]: Keyboard and mouse focus states are easy to see.
AC-05 [FR-05]: The interface remains functional on the current desktop proof size.

## 7. Performance Requirements
- Styling work SHALL not introduce visible scene boot regressions.

## 8. Error Handling
- Missing theme resources SHALL degrade to safe defaults rather than breaking scene load.

## 9. Integration Points
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/*`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless scene tests for focus flow, visible primary actions, and any new theme-dependent nodes that affect critical paths.

## Changelog
- 2026-03-28: Initial Director Mode UI-polish recovery PRD.
