# Backend Slice To Surface Map

This file records the intended primary consumer for each live slice.

## Canonical slices

- `world_state`
  - owns macro world state, active region identity, time progression
- `game_state`
  - owns campaign-wide shell state and current activity mode
- `actors`
  - owns actor roster and actor-specific presentation inputs
- `combat`
  - owns turn order, current turn, legal combat actions, combat outcome feedback
- `dialog_npc`, `dialog_text`, `dialog_options`
  - own dialog presentation
- `world_graph`, `travel_options`, `current_region_summary`
  - own world map travel presentation
- settlement slice
  - owns town pressure, jobs, alerts, stockpiles, residents
- inventory slice
  - owns items, equipment, and usable item actions

## Surface ownership

- Top strip
  - reads `game_state`, `world_state`, and the active player summary only
- World viewport
  - reads map, actor positions, and current focus
- Dialog overlay
  - reads only `dialog_*`
- Combat surface
  - reads only `combat`
- Map tab / travel
  - reads only `world_graph`, `travel_options`, `current_region_summary`
- Town tab
  - reads only settlement slices
- Items tab
  - reads only inventory and equipment slices

## Forbidden synthesis

- Do not synthesize a second combat summary from `actors` when `combat` exists.
- Do not synthesize a second location summary from settlement and map when the top strip already owns location.
- Do not derive dialog state from narrative text if `dialog_options` exists.
