# PRD Implementation Matrix

Generated from `docs/doc_registry.json` via `python -m tools.doc_inventory`.

## Summary

- Active PRDs: 27
- Deprecated PRDs: 56
- Deprecated Notes: 6
- Canonical mechanics map: `docs/architecture/ember_mechanics_canon_v1.md`

## Authoritative PRDs

| Path | Owner | Mechanisms | Runtime Surface | Supersedes |
| --- | --- | --- | --- | --- |
| `docs/prd/active/PRD_actor_kernel_v1.md` | `kernel_actor` | DF:M02, DF:M03, DF:M18, GEMRB:M01 | `frp-backend/engine/kernel/actor.py`, `frp-backend/engine/api/campaign_kernel.py` | - |
| `docs/prd/active/PRD_area_map_v1.md` | `kernel_area` | DF:M16, GEMRB:M10 | `frp-backend/engine/kernel/area.py`, `frp-backend/engine/map` | `docs/deprecated/prd/PRD_map_generator.md`, `docs/deprecated/prd/PRD_pov_system.md` |
| `docs/prd/active/PRD_automation_authority_v1.md` | `qa_automation` | QA:AUTO | `godot-client/tests/automation`, `frp-backend/tests` | `docs/deprecated/prd/PRD_visual_automation_backup_v1.md`, `docs/deprecated/prd/PRD_visual_automation_desktop_executor_v1.md`, `docs/deprecated/prd/PRD_visual_automation_headless_executor_v1.md` |
| `docs/prd/active/PRD_colony_simulation_v2.md` | `kernel_colony` | DF:M03, DF:M11, DF:M12, DF:M16, DF:M19 | `frp-backend/engine/kernel/colony.py`, `frp-backend/engine/api/campaign_state.py` | `docs/deprecated/prd/PRD_colony_simulation_v1.md` |
| `docs/prd/active/PRD_combat_resolution_v1.md` | `kernel_combat` | DF:M01, DF:M03, GEMRB:M02, GEMRB:M03, GEMRB:M04 | `frp-backend/engine/kernel/combat.py`, `frp-backend/engine/core/combat.py` | `docs/deprecated/prd/PRD_combat_engine.md`, `docs/deprecated/prd/PRD_body_injury_combat_v1.md` |
| `docs/prd/active/PRD_creation_surface_v2.md` | `client_creation` | EMBER:CREATION, GEMRB:M16, DF:M03 | `frp-backend/engine/core/character_creation.py`, `godot-client/scenes/title_screen.gd` | `docs/deprecated/prd/PRD_character_system.md`, `docs/deprecated/prd/PRD_game_flow_architecture.md` |
| `docs/prd/active/PRD_dialog_system_v1.md` | `kernel_dialog` | GEMRB:M09 | `frp-backend/engine/kernel/dialog.py`, `frp-backend/engine/api/handlers/social_actions.py` | - |
| `docs/prd/active/PRD_effect_system_v1.md` | `kernel_effects` | DF:M06, DF:M03, GEMRB:M04, GEMRB:M06 | `frp-backend/engine/kernel/effects.py`, `frp-backend/engine/api/game_engine.py` | - |
| `docs/prd/active/PRD_game_state_v1.md` | `kernel_game_state` | GEMRB:M16 | `frp-backend/engine/kernel/game_state.py`, `frp-backend/engine/api/campaign_kernel.py` | - |
| `docs/prd/active/PRD_gamescript_ai_v1.md` | `kernel_scripts` | GEMRB:M08 | `frp-backend/engine/kernel/scripts.py`, `frp-backend/engine/world/behavior_tree.py` | - |
| `docs/prd/active/PRD_godot_client.md` | `client_runtime` | CLIENT:CONTRACT, GEMRB:M16, DF:M15 | `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd`, `godot-client/scenes/title_screen.gd` | `docs/deprecated/prd/PRD_godot_client_sprint_0.md`, `docs/deprecated/prd/PRD_godot_client_sprint_1.md`, `docs/deprecated/prd/PRD_godot_client_sprint_2.md` |
| `docs/prd/active/PRD_history_and_factions_v1.md` | `kernel_history` | DF:M12, DF:M14, DF:M20 | `frp-backend/engine/world/history.py`, `frp-backend/engine/kernel/world_state.py` | `docs/deprecated/prd/PRD_civilizations_institutions_history_v1.md` |
| `docs/prd/active/PRD_hybrid_commander_loop_v1.md` | `kernel_hybrid` | DF:M15, DF:M18, GEMRB:M14, GEMRB:M16 | `frp-backend/engine/kernel/hybrid.py`, `frp-backend/engine/api/campaign_commands.py` | - |
| `docs/prd/active/PRD_item_system_kernel_v1.md` | `kernel_items` | DF:M17, GEMRB:M07 | `frp-backend/engine/kernel/items.py`, `frp-backend/engine/world/inventory.py` | `docs/deprecated/prd/PRD_item_system.md` |
| `docs/prd/active/PRD_job_reaction_kernel_v2.md` | `kernel_jobs` | DF:M02, DF:M04, DF:M16, DF:M19 | `frp-backend/engine/kernel/jobs.py`, `frp-backend/engine/world/crafting.py` | `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md` |
| `docs/prd/active/PRD_level_progression_v1.md` | `kernel_progression` | DF:M02, GEMRB:M15 | `frp-backend/engine/kernel/progression.py`, `frp-backend/engine/core/progression.py` | `docs/deprecated/prd/PRD_progression_system.md` |
| `docs/prd/active/PRD_macro_society_runtime_v1.md` | `kernel_macro_society` | DF:M11, DF:M12, DF:M20, GEMRB:M13, GEMRB:M14 | `frp-backend/engine/api/campaign/live_kernel.py`, `frp-backend/engine/api/campaign/runtime.py`, `frp-backend/engine/kernel/world_state.py` | - |
| `docs/prd/active/PRD_material_item_kernel_v1.md` | `kernel_material_item` | DF:M01, DF:M11, DF:M17, GEMRB:M07 | `frp-backend/engine/kernel/items.py`, `frp-backend/engine/core/item.py` | - |
| `docs/prd/active/PRD_medical_system_v1.md` | `kernel_medical` | DF:M05, DF:M03, DF:M04 | `frp-backend/engine/kernel/medical.py`, `frp-backend/engine/kernel/effects.py` | - |
| `docs/prd/active/PRD_pathfinding_v1.md` | `kernel_pathfinding` | DF:M15, GEMRB:M11 | `frp-backend/engine/kernel/pathfinding.py`, `frp-backend/engine/api/handlers/exploration_navigation.py` | - |
| `docs/prd/active/PRD_save_load.md` | `persistence` | EMBER:SAVELOAD, GEMRB:M16 | `frp-backend/engine/api/save`, `frp-backend/engine/save` | - |
| `docs/prd/active/PRD_spell_system_v1.md` | `kernel_spells` | GEMRB:M05, GEMRB:M06, GEMRB:M12 | `frp-backend/engine/kernel/spells.py`, `frp-backend/engine/kernel/projectiles.py` | `docs/deprecated/prd/PRD_magic_system.md` |
| `docs/prd/active/PRD_STANDARD.md` | `docs_governance` | DOCS:STANDARD | `docs/prd/active/PRD_STANDARD.md` | - |
| `docs/prd/active/PRD_store_trade_v1.md` | `kernel_store` | DF:M11, GEMRB:M13 | `frp-backend/engine/kernel/store.py`, `frp-backend/engine/api/shop_routes.py` | - |
| `docs/prd/active/PRD_systems_closure_v1.md` | `kernel_systems` | DF:M06, DF:M07, DF:M08, DF:M09, DF:M10, DF:M13 | `frp-backend/engine/kernel/systems.py`, `frp-backend/engine/kernel/effects.py` | - |
| `docs/prd/active/PRD_world_data_registries_v1.md` | `data_registries` | DATA:REGISTRY, DF:M14 | `frp-backend/engine/data_loader.py`, `frp-backend/engine/worldgen/registries.py` | - |
| `docs/prd/active/PRD_world_state_kernel_v1.md` | `kernel_world_state` | DF:M11, DF:M12, DF:M14, DF:M20, GEMRB:M14 | `frp-backend/engine/kernel/world_state.py`, `frp-backend/engine/api/campaign_state.py` | `docs/deprecated/prd/PRD_world_state.md`, `docs/deprecated/prd/PRD_live_global_simulation_runtime_v1.md` |

## Deprecated PRDs

- `docs/deprecated/prd/PRD_animation_fluidity_v1.md`
- `docs/deprecated/prd/PRD_api_layer.md`
- `docs/deprecated/prd/PRD_asset_pipeline.md`
- `docs/deprecated/prd/PRD_atmospheric_density_v1.md`
- `docs/deprecated/prd/PRD_biomes_ecology_distribution_v1.md`
- `docs/deprecated/prd/PRD_body_injury_combat_v1.md`
- `docs/deprecated/prd/PRD_campaign_generator.md`
- `docs/deprecated/prd/PRD_character_system.md`
- `docs/deprecated/prd/PRD_civilizations_institutions_history_v1.md`
- `docs/deprecated/prd/PRD_colony_simulation_v1.md`
- `docs/deprecated/prd/PRD_combat_engine.md`
- `docs/deprecated/prd/PRD_consequence_system.md`
- `docs/deprecated/prd/PRD_demo_hook_v1.md`
- `docs/deprecated/prd/PRD_dm_agent.md`
- `docs/deprecated/prd/PRD_dnd_systems_v1.md`
- `docs/deprecated/prd/PRD_game_flow_architecture.md`
- `docs/deprecated/prd/PRD_geology_climate_worldgen_v1.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_0.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_1.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_2.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_3.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_4.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_5.md`
- `docs/deprecated/prd/PRD_godot_client_sprint_6.md`
- `docs/deprecated/prd/PRD_IMPLEMENTATION_MATRIX_legacy_20260401.md`
- `docs/deprecated/prd/PRD_interaction_feedback_v1.md`
- `docs/deprecated/prd/PRD_item_system.md`
- `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md`
- `docs/deprecated/prd/PRD_live_global_simulation_runtime_v1.md`
- `docs/deprecated/prd/PRD_living_simulation_v1.md`
- `docs/deprecated/prd/PRD_living_world_v1.md`
- `docs/deprecated/prd/PRD_magic_system.md`
- `docs/deprecated/prd/PRD_map_generator.md`
- `docs/deprecated/prd/PRD_narrative_presentation_v1.md`
- `docs/deprecated/prd/PRD_npc_agent.md`
- `docs/deprecated/prd/PRD_npc_memory.md`
- `docs/deprecated/prd/PRD_pov_system.md`
- `docs/deprecated/prd/PRD_progression_system.md`
- `docs/deprecated/prd/PRD_projectile_system_v1.md`
- `docs/deprecated/prd/PRD_region_realization_and_settlement_generation_v1.md`
- `docs/deprecated/prd/PRD_rimworld_benchmark_v1.md`
- `docs/deprecated/prd/PRD_scifi_frontier_adapter_v1.md`
- `docs/deprecated/prd/PRD_silhouette_distinctiveness_v1.md`
- `docs/deprecated/prd/PRD_species_lineages_and_content_adapters_v1.md`
- `docs/deprecated/prd/PRD_tile_texture_depth_v1.md`
- `docs/deprecated/prd/PRD_topdown_living_world_v1.md`
- `docs/deprecated/prd/PRD_ui_polish_v1.md`
- `docs/deprecated/prd/PRD_visual_automation_backup_v1.md`
- `docs/deprecated/prd/PRD_visual_automation_desktop_executor_v1.md`
- `docs/deprecated/prd/PRD_visual_automation_headless_executor_v1.md`
- `docs/deprecated/prd/PRD_visual_automation_reporting_v1.md`
- `docs/deprecated/prd/PRD_websocket.md`
- `docs/deprecated/prd/PRD_world_generation_v2.md`
- `docs/deprecated/prd/PRD_world_simulation_architecture_v1.md`
- `docs/deprecated/prd/PRD_world_state.md`
- `docs/deprecated/prd/PRD_worldgen_migration_and_breaking_changes_v1.md`

## Deprecated Notes

- `docs/deprecated/notes/GDD_v1.md`
- `docs/deprecated/notes/GDD_v2.md`
- `docs/deprecated/notes/GDD_v3.md`
- `docs/deprecated/notes/PROMPT_deterministic_world_v1.md`
- `docs/deprecated/notes/PROMPT_director_v2.md`
- `docs/deprecated/notes/PROMPT_visual_automation_ship_executor_v1.md`
