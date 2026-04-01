# Runtime Authority

This diagram defines the current authoritative runtime split for Ember RPG.

```mermaid
flowchart LR
    A["World Graph (authoritative macro state)"] --> B["Campaign Runtime"]
    B --> C["Active Region / Settlement Snapshot"]
    C --> D["GameSession Response Payload"]
    D --> E["GameState"]
    E --> F["World View (active local map)"]
    E --> G["Sidebar Panels"]
    G --> G1["Narrative"]
    G --> G2["Hero"]
    G --> G3["Town"]
    G --> G4["Quests"]
    G --> G5["Items"]
    G --> G6["Map / World Graph"]
```

## Authority Rules

- `WorldBlueprint` and the world graph remain the macro authority.
- Only one local region/settlement is hydrated in detail at a time.
- `SimulationSnapshot.region_states` is the canonical runtime store for:
  - region economy
  - alerts and pressure
  - travel reachability
  - active local runtime enrichments
- `GameState` is the canonical runtime/save-load projection assembled by the
  campaign runtime from typed kernel state. It is not a second independent
  simulation authority, but it is the primary persistence and client handoff
  root for campaign-local play state.
- Campaign payloads should now expose both:
  - typed kernel slices (`world_state`, `actors`, `jobs`, `systems`, ...)
  - a `game_state` root container for save/load round-trip and local runtime continuity
- Sidebar panels must expose distinct layers instead of hiding state inside a
  `TabContainer` tab strip the player has to discover.

## Active Problems This Sprint Fixes

- Character creation state does not yet shape world/campaign setup deeply
- World graph exists but is not discoverable enough in live UI
- Desktop automation depends on an undeclared Windows environment
- Some API/session surfaces still carry legacy compatibility shims even after the
  `GameState` cutover and need follow-up cleanup
