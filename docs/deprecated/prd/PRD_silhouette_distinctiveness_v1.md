# PRD: Silhouette Distinctiveness v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Silhouette Distinctiveness` from `2` to `4` in the first pass by making the player, NPCs, enemies, items, and furniture readable at a glance in the shipped Godot shell. This pass uses existing bundled sprite assets first and avoids backend contract churn unless a failing test proves the client cannot infer a required distinction.

## 2. Scope
- In scope: entity sprite selection, scale, tint discipline, friendly or hostile readability, selection emphasis, furniture or container identity, and player prominence.
- Out of scope: authored animation sheets, combat choreography, or reference-quality portrait art.

## 3. Functional Requirements
FR-01: The player SHALL be visually dominant relative to surrounding actors.
FR-02: Hostile, neutral, friendly, item, and furniture buckets SHALL remain distinguishable without reading labels.
FR-03: Major role archetypes such as warrior, merchant, guard, mage, beast, and container SHALL prefer authored sprites over geometric fallback markers when assets exist.
FR-04: Selection or hover state SHALL increase silhouette legibility rather than obscure it.
FR-05: Missing sprite assets SHALL degrade to explicit fallback markers without crashing rendering.

## 4. Data Structures
```python
class EntityVisualDescriptor(TypedDict):
    entity_id: str
    bucket: str
    template: str
    disposition: str
    is_player: bool
    is_selected: bool
```

## 5. Public API
No external runtime API change is required in the first pass.
Internal consumers:
- `godot-client/scripts/world/entity_layer.gd::render_entities`
- `godot-client/scripts/world/entity_sprite_catalog.gd::resolve_texture`
- `godot-client/scripts/net/response_normalizer.gd` MAY add non-breaking template or disposition normalization only if required by failing tests.

## 6. Acceptance Criteria
AC-01 [FR-01]: In a gameplay screenshot, the player is identifiable within one second without label reading.
AC-02 [FR-02]: At least five on-screen categories remain distinguishable: player, friendly NPC, enemy, item, furniture.
AC-03 [FR-03]: Existing sprite assets are preferred over circle, square, or diamond fallbacks for supported templates.
AC-04 [FR-04]: Hover or selection state improves clarity through outline, contrast, or scale emphasis.
AC-05 [FR-05]: Unsupported templates still render via fallback markers without blank nodes or crashes.

## 7. Performance Requirements
- Entity rendering changes SHALL preserve current scene responsiveness on local Windows hardware.
- Sprite selection SHALL not introduce blocking file IO during normal frame updates.

## 8. Error Handling
- Unknown templates fall back to a visible marker.
- Invalid bucket or disposition values fall back to neutral defaults instead of crashing.

## 9. Integration Points
- `godot-client/scripts/world/entity_layer.gd`
- `godot-client/scripts/world/entity_sprite_catalog.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scripts/net/response_normalizer.gd`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless tests to assert authored sprite preference, player prominence rules, and category-distinct rendering decisions.
- Add or extend automation coverage only after the desktop harness is trustworthy again.

## Changelog
- 2026-03-28: Initial Director Mode silhouette recovery PRD.
