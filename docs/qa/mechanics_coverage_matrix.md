# Mechanics Coverage Matrix

This matrix is the live acceptance tracker for Ember's hybrid mechanics canon.
It replaces fragmented "typed but maybe real" checklists with one shared status
language:

- `missing`: no canonical implementation
- `typed-only`: data shape exists but gameplay logic is incomplete
- `logic-live`: mechanic runs deterministically in the runtime
- `play-validated`: mechanic has automation plus chaotic play coverage

| Family | Owner | Canon Sources | Current Target State |
| --- | --- | --- | --- |
| Actor and progression | `kernel_actor`, `kernel_progression` | DF `M02`; GemRB `M01`, `M15`, `M16` | `logic-live` |
| Combat and wound flow | `kernel_combat`, `kernel_medical`, `kernel_effects` | DF `M01`, `M05`; GemRB `M02`, `M03`, `M04` | `logic-live` |
| Effects and syndromes | `kernel_effects`, `kernel_systems` | DF `M06`; GemRB `M04`, `M06` | `typed-only` |
| Items, equipment, wear | `kernel_items`, `kernel_material_item` | DF `M17`; GemRB `M07` | `logic-live` |
| Dialog and script AI | `kernel_dialog`, `kernel_scripts` | GemRB `M08`, `M09` | `logic-live` |
| Area, rooms, and pathfinding | `kernel_area`, `kernel_pathfinding` | DF `M15`, `M16`; GemRB `M10`, `M11` | `logic-live` |
| Colony, jobs, and farming | `kernel_colony`, `kernel_jobs` | DF `M03`, `M04`, `M16`, `M19` | `typed-only` |
| Trade, migration, diplomacy | `kernel_store`, `kernel_world_state`, `kernel_history` | DF `M11`, `M12`, `M20`; GemRB `M13`, `M14` | `typed-only` |
| Commander loop and military | `kernel_hybrid` | DF `M15`, `M18`; GemRB `M14`, `M16` | `logic-live` |
| Systems closure | `kernel_systems` | DF `M07`, `M08`, `M09`, `M10`, `M13` | `typed-only` |
| Save/load and runtime continuity | `persistence`, `kernel_game_state` | GemRB `M16`; DF `M14` | `logic-live` |
| Godot client contract | `client_runtime`, `client_creation` | Ember-specific | `logic-live` |

## Acceptance Rule

No family moves to `play-validated` until:

1. the active PRD exists under `docs/prd/active/`
2. the runtime owner module is canonical and serialized
3. targeted tests are green
4. chaotic play covers the mechanic without state loss or authority drift
