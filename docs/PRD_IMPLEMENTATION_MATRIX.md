# PRD Implementation Matrix

Generated from `docs/doc_registry.json` via `python -m tools.doc_inventory`.

## Summary

- Active PRDs: 94
- Deprecated PRDs: 0
- Deprecated Notes: 0
- Canonical mechanics map: `docs/architecture/ember_mechanics_canon_v1.md`

## Authoritative PRDs

| Path | Owner | Mechanisms | Runtime Surface | Supersedes |
| --- | --- | --- | --- | --- |
| `docs/prd/active/PRD_actor_kernel_v1.md` | `kernel_actor` | DF:M02, DF:M03, DF:M18, GEMRB:M01 | `frp-backend/engine/kernel/actor.py`, `frp-backend/engine/api/campaign_kernel.py` | - |
| `docs/prd/active/PRD_actor_record_authority_v1.md` | `kernel_actor` | DF:M02, GEMRB:M01 | `frp-backend/engine/kernel/actor_records.py`, `frp-backend/engine/api/campaign_kernel.py` | - |
| `docs/prd/active/PRD_api_handler_cleanup_v1.md` | `runtime_cleanup` | EMBER:CLEANUP | `frp-backend/engine/api/campaign/runtime_commands.py` | - |
| `docs/prd/active/PRD_architecture_actor_animation_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_actor_runtime_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_actor_spawning_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_ambient_life_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_area_ambient_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_effect_visualization_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_fast_visual_tick_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_pathfinding_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_architecture_sprite_layers_v1.md` | `client_architecture` | CLIENT:ARCH | `frp-backend/engine/api/campaign/runtime.py`, `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_area_map_v1.md` | `kernel_area` | DF:M16, GEMRB:M10 | `frp-backend/engine/kernel/area.py`, `frp-backend/engine/map` | `docs/deprecated/prd/PRD_map_generator.md`, `docs/deprecated/prd/PRD_pov_system.md` |
| `docs/prd/active/PRD_automation_authority_v1.md` | `qa_automation` | QA:AUTO | `godot-client/tests/automation`, `frp-backend/tests` | `docs/deprecated/prd/PRD_visual_automation_backup_v1.md`, `docs/deprecated/prd/PRD_visual_automation_desktop_executor_v1.md`, `docs/deprecated/prd/PRD_visual_automation_headless_executor_v1.md` |
| `docs/prd/active/PRD_campaign_combat_turn_economy_v1.md` | `kernel_combat` | DF:M01, GEMRB:M02, GEMRB:M03 | `frp-backend/engine/kernel/combat_engine.py`, `frp-backend/engine/api/combat_bridge.py` | - |
| `docs/prd/active/PRD_campaign_runtime_authority_v1.md` | `runtime_campaign` | EMBER:RUNTIME | `frp-backend/engine/api/campaign/runtime.py`, `frp-backend/engine/api/campaign/context.py` | - |
| `docs/prd/active/PRD_campaign_save_schema_v3.md` | `persistence` | EMBER:SAVELOAD | `frp-backend/engine/api/save` | - |
| `docs/prd/active/PRD_character_creation_v2.md` | `client_creation_ux` | CLIENT:CREATION:UX, GEMRB:M16, DF:M12 | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd`, `frp-backend/engine/core/character_creation.py` | - |
| `docs/prd/active/PRD_colony_simulation_v2.md` | `kernel_colony` | DF:M03, DF:M11, DF:M12, DF:M16, DF:M19 | `frp-backend/engine/kernel/colony.py`, `frp-backend/engine/api/campaign/settlement.py` | `docs/deprecated/prd/PRD_colony_simulation_v1.md` |
| `docs/prd/active/PRD_combat_resolution_v1.md` | `kernel_combat` | DF:M01, DF:M03, GEMRB:M02, GEMRB:M03, GEMRB:M04 | `frp-backend/engine/kernel/combat.py`, `frp-backend/engine/core/combat.py` | `docs/deprecated/prd/PRD_combat_engine.md`, `docs/deprecated/prd/PRD_body_injury_combat_v1.md` |
| `docs/prd/active/PRD_creation_surface_v2.md` | `client_creation` | EMBER:CREATION, GEMRB:M16, DF:M03 | `frp-backend/engine/core/character_creation.py`, `godot-client/scenes/title_screen.gd` | `docs/deprecated/prd/PRD_character_system.md`, `docs/deprecated/prd/PRD_game_flow_architecture.md` |
| `docs/prd/active/PRD_data_externalization_v1.md` | `data_registries` | DATA:REGISTRY | `frp-backend/data`, `frp-backend/engine/data_loader.py` | - |
| `docs/prd/active/PRD_dialog_system_v1.md` | `kernel_dialog` | GEMRB:M09 | `frp-backend/engine/kernel/dialog.py`, `frp-backend/engine/api/handlers/social_actions.py` | - |
| `docs/prd/active/PRD_effect_system_v1.md` | `kernel_effects` | DF:M06, DF:M03, GEMRB:M04, GEMRB:M06 | `frp-backend/engine/kernel/effects.py`, `frp-backend/engine/api/game_engine.py` | - |
| `docs/prd/active/PRD_frontend_action_bar_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_area_map_ui_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_ask_about_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_ask_dm_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_character_creation_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_character_record_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_clock_widget_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_creation_abilities_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_alignment_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_class_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_finalize_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_gender_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_name_bio_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_portrait_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_proficiencies_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_race_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_skills_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_sound_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_creation_spells_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_death_screen_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_dev_console_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_dual_class_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_exploration_view_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_extraction_index_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_inventory_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_journal_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_level_up_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_load_ui_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_loading_screen_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_mage_spellbook_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_message_window_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_options_menu_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_party_portraits_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_priest_spellbook_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_quit_confirm_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_save_ui_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_sniped_shot_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_think_panel_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_title_menu_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/title_screen.gd`, `godot-client/scripts/ui/creation_wizard.gd` | - |
| `docs/prd/active/PRD_frontend_tooltip_system_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_frontend_world_map_v1.md` | `client_frontend` | CLIENT:UX | `godot-client/scenes/game_session.gd`, `godot-client/autoloads/game_state.gd`, `godot-client/scripts/world/world_view.gd` | - |
| `docs/prd/active/PRD_game_state_v1.md` | `kernel_game_state` | GEMRB:M16 | `frp-backend/engine/kernel/game_state.py`, `frp-backend/engine/api/campaign_kernel.py` | - |
| `docs/prd/active/PRD_gamescript_ai_v1.md` | `kernel_scripts` | GEMRB:M08 | `frp-backend/engine/kernel/scripts.py`, `frp-backend/engine/world/behavior_tree.py` | - |
| `docs/prd/active/PRD_godot_campaign_shell_contract_v1.md` | `client_runtime` | CLIENT:CONTRACT | `godot-client/autoloads/backend.gd`, `godot-client/scenes/game_session.gd` | - |
| `docs/prd/active/PRD_godot_client.md` | `client_runtime` | CLIENT:CONTRACT, GEMRB:M16, DF:M15 | `godot-client/autoloads/game_state.gd`, `godot-client/scenes/game_session.gd`, `godot-client/scenes/title_screen.gd` | `docs/deprecated/prd/PRD_godot_client_sprint_0.md`, `docs/deprecated/prd/PRD_godot_client_sprint_1.md`, `docs/deprecated/prd/PRD_godot_client_sprint_2.md` |
| `docs/prd/active/PRD_godot_ux_accessibility_v1.md` | `client_ux` | CLIENT:UX, CLIENT:ACCESSIBILITY | `godot-client/scenes/title_screen.gd`, `godot-client/scenes/game_session.gd`, `godot-client/tests/automation` | - |
| `docs/prd/active/PRD_history_and_factions_v1.md` | `kernel_history` | DF:M12, DF:M14, DF:M20 | `frp-backend/engine/world/history.py`, `frp-backend/engine/kernel/world_state.py` | `docs/deprecated/prd/PRD_civilizations_institutions_history_v1.md` |
| `docs/prd/active/PRD_hybrid_commander_loop_v1.md` | `kernel_hybrid` | DF:M15, DF:M18, GEMRB:M14, GEMRB:M16 | `frp-backend/engine/kernel/hybrid.py`, `frp-backend/engine/api/campaign_commands.py` | - |
| `docs/prd/active/PRD_IMPLEMENTATION_MATRIX.md` | `docs_governance` | DOCS:MATRIX | `docs/PRD_IMPLEMENTATION_MATRIX.md`, `docs/doc_registry.json`, `frp-backend/tools/doc_inventory.py` | `docs/deprecated/prd/PRD_IMPLEMENTATION_MATRIX_legacy_20260401.md` |
| `docs/prd/active/PRD_item_system_kernel_v1.md` | `kernel_items` | DF:M17, GEMRB:M07 | `frp-backend/engine/kernel/items.py`, `frp-backend/engine/world/inventory.py` | `docs/deprecated/prd/PRD_item_system.md` |
| `docs/prd/active/PRD_job_reaction_kernel_v2.md` | `kernel_jobs` | DF:M02, DF:M04, DF:M16, DF:M19 | `frp-backend/engine/kernel/jobs.py`, `frp-backend/engine/world/crafting.py` | `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md` |
| `docs/prd/active/PRD_kernel_combat_engine_v1.md` | `kernel_combat` | DF:M01, GEMRB:M02 | `frp-backend/engine/kernel/combat_engine.py` | - |
| `docs/prd/active/PRD_legacy_deletion_v1.md` | `runtime_cleanup` | EMBER:CLEANUP | `frp-backend/engine/api/campaign` | - |
| `docs/prd/active/PRD_level_progression_v1.md` | `kernel_progression` | DF:M02, GEMRB:M15 | `frp-backend/engine/kernel/progression.py`, `frp-backend/engine/core/progression.py` | `docs/deprecated/prd/PRD_progression_system.md` |
| `docs/prd/active/PRD_macro_society_runtime_v1.md` | `kernel_macro_society` | DF:M11, DF:M12, DF:M20, GEMRB:M13, GEMRB:M14 | `frp-backend/engine/api/campaign/live_kernel.py`, `frp-backend/engine/api/campaign/runtime_macro_society.py`, `frp-backend/engine/kernel/world_state.py` | - |
| `docs/prd/active/PRD_material_item_kernel_v1.md` | `kernel_material_item` | DF:M01, DF:M11, DF:M17, GEMRB:M07 | `frp-backend/engine/kernel/items.py`, `frp-backend/engine/core/item.py` | - |
| `docs/prd/active/PRD_medical_system_v1.md` | `kernel_medical` | DF:M05, DF:M03, DF:M04 | `frp-backend/engine/kernel/medical.py`, `frp-backend/engine/kernel/effects.py` | - |
| `docs/prd/active/PRD_pathfinding_v1.md` | `kernel_pathfinding` | DF:M15, GEMRB:M11 | `frp-backend/engine/kernel/pathfinding.py`, `frp-backend/engine/api/handlers/exploration_navigation.py` | - |
| `docs/prd/active/PRD_PLAYABILITY_RESCUE.md` | `runtime_campaign` | EMBER:RUNTIME | `frp-backend/engine/api/campaign/runtime_commands.py`, `frp-backend/tests/test_playability_contract.py` | - |
| `docs/prd/active/PRD_save_load.md` | `persistence` | EMBER:SAVELOAD, GEMRB:M16 | `frp-backend/engine/api/save`, `frp-backend/engine/save` | - |
| `docs/prd/active/PRD_save_schema_v4.md` | `persistence` | EMBER:SAVELOAD | `frp-backend/engine/api/save`, `frp-backend/engine/save/save_models.py` | `docs/prd/active/PRD_campaign_save_schema_v3.md` |
| `docs/prd/active/PRD_spell_system_v1.md` | `kernel_spells` | GEMRB:M05, GEMRB:M06, GEMRB:M12 | `frp-backend/engine/kernel/spells.py`, `frp-backend/engine/kernel/projectiles.py` | `docs/deprecated/prd/PRD_magic_system.md` |
| `docs/prd/active/PRD_STANDARD.md` | `docs_governance` | DOCS:STANDARD | `docs/prd/active/PRD_STANDARD.md` | - |
| `docs/prd/active/PRD_stat_unification_v1.md` | `kernel_actor` | DF:M02, GEMRB:M01 | `frp-backend/engine/kernel/actor_records.py`, `frp-backend/data/classes.json` | - |
| `docs/prd/active/PRD_store_trade_v1.md` | `kernel_store` | DF:M11, GEMRB:M13 | `frp-backend/engine/kernel/store.py`, `frp-backend/engine/api/shop_routes.py` | - |
| `docs/prd/active/PRD_systems_closure_v1.md` | `kernel_systems` | DF:M06, DF:M07, DF:M08, DF:M09, DF:M10, DF:M13 | `frp-backend/engine/kernel/systems.py`, `frp-backend/engine/kernel/effects.py` | - |
| `docs/prd/active/PRD_ux_gameplay_v1.md` | `client_gameplay_ux` | CLIENT:GAMEPLAY:UX, GEMRB:M09, GEMRB:M10, DF:M15 | `godot-client/scenes/game_session.gd`, `godot-client/scripts/world/world_view.gd`, `godot-client/scripts/ui/dialog_overlay.gd` | - |
| `docs/prd/active/PRD_websocket_transport_v1.md` | `runtime_transport` | EMBER:WS | `frp-backend/engine/api/ws_campaign.py` | - |
| `docs/prd/active/PRD_world_data_registries_v1.md` | `data_registries` | DATA:REGISTRY, DF:M14 | `frp-backend/engine/data_loader.py`, `frp-backend/engine/worldgen/registries.py` | - |
| `docs/prd/active/PRD_world_state_kernel_v1.md` | `kernel_world_state` | DF:M11, DF:M12, DF:M14, DF:M20, GEMRB:M14 | `frp-backend/engine/kernel/world_state.py`, `frp-backend/engine/api/campaign/world.py` | `docs/deprecated/prd/PRD_world_state.md`, `docs/deprecated/prd/PRD_live_global_simulation_runtime_v1.md` |

## Deprecated PRDs


## Deprecated Notes

