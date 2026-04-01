# PRD: Tile Texture Depth v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Tile Texture Depth` from `3` to `4` in the first pass by making terrain, roads, interiors, and prop tiles read as surfaces rather than wallpaper. This pass prioritizes the existing tile asset library and placeholder-map honesty before asking for new art.

## 2. Scope
- In scope: tile asset preference, fallback tile drawing quality, road and floor readability, basic variety reduction for repeated surfaces, and explicit placeholder-map presentation.
- Out of scope: biome simulation, procedural history stains, or large new terrain systems.

## 3. Functional Requirements
FR-01: Core terrain types SHALL prefer bundled tile art when assets exist.
FR-02: Fallback tiles SHALL look deliberate and readable, not like flat debug fills.
FR-03: Repeated terrain SHALL include enough tonal or pattern variation to reduce wallpaper repetition.
FR-04: Doors, wells, fountains, barrels, chests, anvils, beds, and similar interactive tiles SHALL remain easy to spot.
FR-05: Placeholder maps SHALL remain visually distinct from live campaign maps.

## 4. Data Structures
```python
class TileVisualRule(TypedDict):
    tile_name: str
    asset_path: str | None
    fallback_palette_key: str
    interactive: bool
    placeholder_safe: bool
```

## 5. Public API
No external route or payload change is required.
Internal consumers:
- `godot-client/scripts/world/tile_catalog.gd`
- `godot-client/scripts/world/tilemap_controller.gd`
- `godot-client/scripts/world/world_view.gd`

## 6. Acceptance Criteria
AC-01 [FR-01]: Grass, stone, wood, path, water, and wall tiles render from bundled art when present.
AC-02 [FR-02]: Missing art still renders through a readable fallback tile style.
AC-03 [FR-03]: Baseline gameplay screenshots no longer read as a single repeated grass texture with one stamped building block.
AC-04 [FR-04]: Interactive terrain-embedded objects remain easy to identify in the world view.
AC-05 [FR-05]: Placeholder maps are obviously placeholder at first glance.

## 7. Performance Requirements
- Tile building SHALL remain fast enough for current map sizes without a visible boot hitch.

## 8. Error Handling
- Missing tile assets fall back to generated tiles.
- Unknown tile names resolve deterministically and visibly.

## 9. Integration Points
- `godot-client/scripts/world/tile_catalog.gd`
- `godot-client/scripts/world/tilemap_controller.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/assets/tiles/*`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless tests around tile asset preference, placeholder labeling, and interactive tile visibility.

## Changelog
- 2026-03-28: Initial Director Mode tile-depth recovery PRD.
