# PRD: Atmospheric Density v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Atmospheric Density` from `1` to `3` in the first pass by adding low-cost mood layers to the title screen and gameplay shell. This is a presentation pass, not a full lighting system.

## 2. Scope
- In scope: adapter-aware ambience, subtle overlays, vignettes, title and world mood treatment, and lightweight environmental effects.
- Out of scope: full dynamic lighting, weather simulation, or reference-quality particles.

## 3. Functional Requirements
FR-01: The title screen SHALL have a deliberate atmosphere instead of a flat dark background.
FR-02: Gameplay SHALL expose adapter-aware mood through tint, vignette, or overlay work that does not destroy readability.
FR-03: Placeholder or no-data states SHALL remain clearly labeled and visually distinct.
FR-04: The first pass MAY use lightweight particles or animated overlays, but they SHALL remain optional and non-blocking.

## 4. Data Structures
```python
class AtmosphereProfile(TypedDict):
    adapter_id: str
    background_color: str
    vignette_strength: float
    overlay_color: str
```

## 5. Public API
No public API change.
Internal surfaces MAY expose helper methods for applying adapter-specific atmosphere profiles.

## 6. Acceptance Criteria
AC-01 [FR-01]: Fresh title screenshots no longer read as an empty black-purple void.
AC-02 [FR-02]: `fantasy_ember` and `scifi_frontier` feel visually different within one screenshot.
AC-03 [FR-03]: Placeholder maps remain honest and distinct after atmosphere layers are added.
AC-04 [FR-04]: Any atmospheric motion remains lightweight and does not break existing headless or desktop flows.

## 7. Performance Requirements
- Added overlays or particles SHALL not introduce a noticeable input delay or scene hitch.

## 8. Error Handling
- If a mood asset or overlay fails to load, the client falls back to readable static colors.

## 9. Integration Points
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scripts/ui/minimap_panel.gd`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless scene-instantiation coverage so atmosphere layers do not break title or gameplay scene startup.

## Changelog
- 2026-03-28: Initial Director Mode atmosphere recovery PRD.
