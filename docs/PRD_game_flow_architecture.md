# PRD: Game Flow Architecture — The Living DM Experience
# This is the CORE DESIGN DOCUMENT for how the game actually FEELS to play
# Priority: CRITICAL — This defines the player experience

## 1. Vision

Like a real tabletop RPG session: the DM narrates, the world materializes,
the player explores through words AND clicks. Everything streams in
dynamically — map, NPCs, items, descriptions — as the DM reveals them.

Think: Point-and-click adventure (Monkey Island) + Tabletop RPG + AI DM

## 2. The Player Experience (Step by Step)

### Game Start
```
[Screen: Dark, empty]

DM: "You awaken to the sound of crashing waves. Salt air fills your lungs.
     As your eyes adjust, you find yourself on a rocky shore..."

[Tile map fades in: beach tiles, water on one side]

DM: "To the north, a weathered stone path leads uphill toward
     a cluster of buildings — a small harbor town."

[Path tiles appear, town silhouette in the distance]
[Clickable elements appear: "path north", "rocky shore", "strange object"]

DM: "At your feet, half-buried in sand, you notice something glinting
     in the morning light."

[Item sprite appears on map: mysterious object]
```

### Player Interaction (3 modes, all valid simultaneously)

**Mode 1: Text Input (FRP style)**
```
Player types: "pick up the glinting object"
→ Action Parser → examine/pickup action
→ Game Engine → item added to inventory
→ DM narrates result
→ UI updates (inventory, map)
```

**Mode 2: Click on Map (Point-and-click style)**
```
Player clicks on [mysterious object] on map
→ Context menu appears:
  [Examine] [Pick up] [Kick] [Ignore]
→ Player clicks [Pick up]
→ Same pipeline as text input
→ DM narrates, UI updates
```

**Mode 3: Click on NPC (Dialogue style)**
```
Player clicks on [merchant] sprite on map
→ NPC panel opens (portrait, name, mood indicator)
→ Context menu: [Talk] [Trade] [Pickpocket] [Attack]
→ Player clicks [Talk]
→ NPC Dialogue Agent generates conversation
→ Player can type responses OR click suggested options
```

## 3. Subagent Architecture

Each concern is handled by a SEPARATE subagent. They don't mix.

```
┌─────────────────────────────────────────────┐
│              ORCHESTRATOR                     │
│  Coordinates all subagents, manages flow      │
│  Model: Claude Sonnet (1x premium)            │
├─────────────────────────────────────────────┤
│                                               │
│  ┌──────────────┐  ┌──────────────────┐      │
│  │ DM_NARRATOR  │  │ MAP_GENERATOR    │      │
│  │              │  │                  │      │
│  │ Narrates     │  │ Creates tile     │      │
│  │ scenes,      │  │ layouts for      │      │
│  │ describes    │  │ rooms, areas,    │      │
│  │ atmosphere   │  │ dungeons         │      │
│  │              │  │                  │      │
│  │ Model:       │  │ Model:           │      │
│  │ Haiku (0.3x) │  │ Deterministic    │      │
│  │ or Sonnet    │  │ + Haiku seed     │      │
│  └──────────────┘  └──────────────────┘      │
│                                               │
│  ┌──────────────┐  ┌──────────────────┐      │
│  │ ENTITY_PLACER│  │ NPC_DIALOGUE     │      │
│  │              │  │                  │      │
│  │ Places NPCs, │  │ Handles NPC      │      │
│  │ items, enemies│  │ conversations    │      │
│  │ on map based  │  │ with memory +    │      │
│  │ on scene      │  │ personality      │      │
│  │              │  │                  │      │
│  │ Model:       │  │ Model:           │      │
│  │ Deterministic│  │ Haiku (routine)  │      │
│  │ + templates  │  │ Sonnet (key NPC) │      │
│  └──────────────┘  └──────────────────┘      │
│                                               │
│  ┌──────────────┐  ┌──────────────────┐      │
│  │ COMBAT_MGR   │  │ WORLD_STATE      │      │
│  │              │  │                  │      │
│  │ Turn-based   │  │ Tracks all       │      │
│  │ combat flow  │  │ changes,         │      │
│  │ mechanics    │  │ consequences,    │      │
│  │              │  │ NPC memory       │      │
│  │ Model:       │  │                  │      │
│  │ Deterministic│  │ Model:           │      │
│  │ (dice+rules) │  │ Pure data        │      │
│  └──────────────┘  └──────────────────┘      │
│                                               │
└─────────────────────────────────────────────┘
```

## 4. The Scene Reveal Flow (Technical)

When player enters a new area:

### Step 1: Orchestrator decides scene type
```python
# Orchestrator receives: player entered "harbor_town"
scene_request = {
    "location": "harbor_town",
    "player": player_state,
    "world_state": world_state,
    "time_of_day": "morning"
}
```

### Step 2: MAP_GENERATOR creates layout (deterministic + seed)
```python
# Returns tile grid + room definitions
map_data = {
    "tiles": [[tile_type for col] for row],  # 2D grid
    "rooms": [
        {"id": "tavern", "bounds": [3,2,8,6], "type": "building"},
        {"id": "market", "bounds": [10,3,15,7], "type": "outdoor"},
        {"id": "docks", "bounds": [0,8,15,12], "type": "water_edge"}
    ],
    "connections": [{"from": "tavern", "to": "market", "type": "door"}]
}
```

### Step 3: ENTITY_PLACER populates the map
```python
# Based on location templates + randomization
entities = {
    "npcs": [
        {"id": "merchant_tom", "template": "merchant", "position": [12,5]},
        {"id": "guard_1", "template": "guard", "position": [8,4]},
        {"id": "innkeeper", "template": "innkeeper", "position": [5,3]}
    ],
    "items": [
        {"id": "barrel_1", "type": "container", "position": [11,6]},
        {"id": "notice_board", "type": "interactive", "position": [9,5]}
    ],
    "enemies": []  # peaceful area, no enemies
}
```

### Step 4: DM_NARRATOR describes the scene
```python
# Input: map_data + entities + world_state + player_state
# Output: streaming narrative text

narrative = dm_narrator.narrate(
    context={
        "scene": "harbor_town",
        "map": map_data,
        "entities": entities,
        "world_state": world_state,
        "player": player_state,
        "instruction": "Describe this scene atmospherically. Reveal key elements gradually."
    }
)
# Returns: "The morning sun casts long shadows across Harbor Town's cobblestone streets..."
```

### Step 5: Godot client renders progressively
```
[DM starts narrating]
→ Background color changes (dark → morning light)
→ Base tiles fade in (ground, water, buildings)
→ As DM mentions "market stalls" → market sprites appear
→ As DM mentions "a weathered guard" → guard NPC appears
→ As DM mentions "notice board" → notice board clickable
→ Narrative complete → ALL elements interactive
```

## 5. Context Menu System (Click Interaction)

### On Map Tile Click:
```
Right-click on empty tile:
  [Move here] [Examine area]

Right-click on NPC:
  [Talk] [Examine] [Trade*] [Attack] [Pickpocket*]
  (* only if applicable)

Right-click on item:
  [Examine] [Pick up] [Use] [Break]

Right-click on door:
  [Open] [Lock pick*] [Break down] [Listen]
  (* only for Rogue class)
```

### On Inventory Item Click:
```
Right-click on item in inventory:
  [Use] [Equip] [Drop] [Examine] [Throw]
```

## 6. Streaming Architecture

The key insight: elements appear on screen AS the DM narrates.

### API Response Format (Streaming)
```json
{
    "narrative_stream": [
        {"text": "The morning sun casts long shadows...", "delay_ms": 0},
        {"text": "A weathered guard stands near the gate.", "delay_ms": 2000,
         "reveal": {"type": "npc", "id": "guard_1"}},
        {"text": "Market stalls line the eastern road.", "delay_ms": 4000,
         "reveal": {"type": "area", "id": "market"}},
        {"text": "Something catches your eye on the notice board.", "delay_ms": 6000,
         "reveal": {"type": "item", "id": "notice_board", "highlight": true}}
    ],
    "map_data": {...},
    "entities": {...},
    "available_actions": ["examine", "move", "talk"]
}
```

### Godot Client Handling
```gdscript
# Receive scene data
# Render base map (hidden/fog)
# Start narrative text crawl
# On each reveal trigger: animate element appearing
# After narrative: enable all interactions
```

## 7. Separation of Concerns

| Concern | Who Handles | Model Cost |
|---------|------------|------------|
| Scene narrative | DM_NARRATOR | Haiku (0.33x) |
| Map layout | MAP_GENERATOR | Deterministic (0x) |
| NPC/item placement | ENTITY_PLACER | Deterministic (0x) |
| NPC conversation | NPC_DIALOGUE | Haiku routine, Sonnet key (0.33-1x) |
| Combat mechanics | COMBAT_MGR | Deterministic (0x) |
| Combat narration | DM_NARRATOR | Haiku (0.33x) |
| World state updates | WORLD_STATE | Pure data (0x) |
| Action parsing | ACTION_PARSER | Deterministic + Haiku fallback |
| Quest generation | ORCHESTRATOR | Sonnet (1x, rare) |

**Per-scene cost estimate:** ~2-3 Haiku calls = ~1 premium req

## 8. Acceptance Criteria

### AC-1: Scene Reveal
- [ ] New area → DM narrates while map progressively reveals
- [ ] Elements appear timed with narrative
- [ ] After reveal, all elements interactive

### AC-2: Three Interaction Modes
- [ ] Text input works for all actions
- [ ] Right-click context menu on all map elements
- [ ] NPC click opens dialogue panel
- [ ] All three modes produce identical game outcomes

### AC-3: Subagent Isolation
- [ ] DM_NARRATOR never modifies game state
- [ ] MAP_GENERATOR never narrates
- [ ] COMBAT_MGR handles only mechanics, DM narrates results
- [ ] Each subagent callable independently

### AC-4: Progressive Rendering
- [ ] Map tiles fade in (not instant pop)
- [ ] NPC sprites animate on appearance
- [ ] Text scrolls at readable speed
- [ ] Player can skip/fast-forward

### AC-5: Context Menus
- [ ] Right-click shows relevant actions only
- [ ] Class-specific options (Rogue: pickpocket, Mage: detect magic)
- [ ] Disabled options shown grayed out with reason

## 9. Dependencies
- Phase 3 (World State, NPC Memory, Consequences) ✅
- Phase 4 (LLM Integration) ✅
- Godot Client base ✅
- Asset sprites ✅

## 10. Implementation Order
1. Backend: Orchestrator endpoint that coordinates all subagents
2. Backend: Streaming response format for scene reveals
3. Godot: Progressive tile map renderer
4. Godot: Context menu system (right-click)
5. Godot: NPC dialogue panel
6. Godot: Narrative text crawl with reveal triggers
7. Integration: Connect Godot ↔ Backend streaming
