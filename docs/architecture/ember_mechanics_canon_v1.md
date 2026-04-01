# Ember Mechanics Canon v1

This document is Ember RPG's canonical interpretation layer for the two external
mechanics frameworks supplied to the project. The source frameworks are treated
as analysis input only. Ember's implementation, naming, and runtime contracts
remain genre-agnostic and repo-owned.

## Principles

- Deterministic simulation is authoritative. Narrative and conversation adapters
  may describe state but never create gameplay outcomes.
- Ember uses one shared game-state flow for avatar play, commander decisions,
  colony simulation, travel, and save/load.
- Overlapping mechanics are resolved with an `Ember Hybrid` rule: use the part
  of each source family that best preserves state coherence, inspectability, and
  extensibility.
- Source references stay at the mechanic-family level only, never as branded
  content or copied rules text.

## Runtime Roots

The simulation is normalized around these roots:

- `GameState`: top-level campaign/session authority
- `WorldState`: macro graph, regions, sites, factions, history, diplomacy
- `AreaState`: currently hydrated local map, rooms, doors, spawns, fog, context
- `ActorState`: avatar, NPC, creature, body, skills, loadout, conditions
- `ColonyState`: needs, shortages, morale, production, rooms, jobs, migration
- `CommandState`: travel plans, squad orders, settlement directives
- `EffectState`: buffs, debuffs, syndromes, saves, timed conditions

## Canonical Mechanic Ownership

| Ember Subsystem | Canonical Choice | Source Families |
| --- | --- | --- |
| Actor and progression | GemRB-style party/class progression blended with DF-style skill growth and rust | DF `M02`, GemRB `M01`, `M15`, `M16` |
| Combat and wounds | GemRB accuracy, initiative, AC, saves, spells; DF tissue, materials, pain, blood loss, casualty fallout | DF `M01`, `M03`, `M05`, GemRB `M02`, `M03`, `M04`, `M05`, `M12` |
| Effects and syndromes | Single Ember effect queue for opcodes, conditions, syndromes, durations, and resistance gates | DF `M06`, GemRB `M04`, `M06` |
| Items, equipment, and wear | GemRB slot/header/usability model blended with DF wear, quality, and material behavior | DF `M17`, GemRB `M07` |
| Dialog and script AI | GemRB-style deterministic dialog and script evaluation; no freeform runtime state changes from LLM | GemRB `M08`, `M09` |
| Area, pathfinding, and travel | GemRB local area/search map model blended with DF movement cost, room semantics, and macro travel continuity | DF `M15`, `M16`, GemRB `M10`, `M11`, `M14` |
| Colony and jobs | DF needs, moods, jobs, rooms, shortages, trade, farming, migration, diplomacy | DF `M03`, `M04`, `M11`, `M12`, `M16`, `M19`, `M20` |
| Systems closure | DF power, traps, fluids, temperature, and strange moods adapted into typed Ember kernels | DF `M07`, `M08`, `M09`, `M10`, `M13` |
| Save/load and campaign continuity | GemRB-style root game-state persistence with Ember kernel snapshots | GemRB `M16`, DF `M14` |

## Overlap Decisions

- Attack resolution uses GemRB-style attack timing and defense gates before any
  DF-style wound physics. A miss never enters tissue simulation.
- Skills advance from usage and jobs in DF fashion, but class levels, slots,
  and party-facing milestones use GemRB-style progression surfaces.
- Stores and services use GemRB interaction framing, while prices and stock
  pressure are driven by DF-style supply and colony state.
- Macro travel, world-map continuity, and active-site hydration use GemRB's
  readable world-map framing but remain driven by DF-style persistent world
  state and time advance.
- Colony simulation is not a side mode. Local avatar actions and commander
  directives advance the same deterministic clock.

## Canonical Active PRD Families

- Creation and commander identity
- Actor and progression
- Combat, effects, and medical
- Items, spells, and store
- Dialog and script AI
- Area, pathfinding, and travel
- Colony, jobs, rooms, farming, migration, diplomacy
- Game state, save/load, and runtime authority
- Godot client contract and automation authority

## Non-Goals

- Copying source code structure, branded terminology, or copyrighted content
- Allowing any LLM path to mutate authoritative simulation state
- Keeping multiple PRD families active for the same mechanic once a canonical
  Ember owner exists
