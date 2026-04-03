**Hedef Mimari** (COMPLETED)
- World creation tamamen soru-cevap tabanlı. CreationState kernel'de Q&A + weight accumulation + genesis/hints üretiyor.
- Runtime canlı. CampaignTickLoop async background tick, combat dışında world kendiliğinden ilerliyor.
- WebSocket birincil runtime transport. HTTP sadece creation/bootstrap/save/load için.
- Commerce gerçek: buy/sell/rent/identify kernel store.py üzerinden çalışıyor.
- Dialog authority: kernel dialog tree (DialogDef state machine), sentetik overlay silindi.
- Spellcasting kernel pipeline: inline Magic Missile hack silindi, begin_casting/resolve_cast kullanılıyor.
- Medical kernel'e bağlı: diagnose/treat commands, check_lethal_conditions tick'te çalışıyor.
- Legacy session-first yüzeyler silindi: routes.py, shop_routes.py, inventory_routes.py, save_routes.py, npc_memory_routes.py, scene_routes.py, models.py, world_routes.py.

**DONE**
1. ✅ CreationState: Q&A flow, weight accumulation, recommended outputs, genesis/hints, to_dict() — 25 tests pass.
2. ✅ CampaignTickLoop: async background tick, pause/resume, combat-aware — 10 tests pass.
3. ✅ runtime.py refactored under 450 lines: run_command extracted to runtime_commands.py.
4. ✅ WebSocket wired: set_runtime() via FastAPI lifespan, connection registry, tick event push — 6 tests pass.
5. ✅ Dialog authority: kernel DialogDef bridge, stat-check conditions, fallback for generic NPCs — 8 tests pass.
6. ✅ Commerce: buy/sell/rent/identify via kernel store.py buy_item/sell_item — 6 tests pass.
7. ✅ Spell pipeline: kernel begin_casting/resolve_cast replaces inline Magic Missile — 2 tests pass.
8. ✅ Medical: diagnose/treat commands via kernel medical.py, check_lethal_conditions — 4 tests pass.
9. ✅ Legacy deletion: 8 route files + 5 legacy test files deleted, no legacy imports guard — 2 tests pass.
10. ✅ 65 new tests total, all passing.

**Deleted Files**
- engine/api/routes.py (359 lines)
- engine/api/models.py
- engine/api/shop_routes.py (233 lines)
- engine/api/inventory_routes.py (131 lines)
- engine/api/save_routes.py (220 lines)
- engine/api/npc_memory_routes.py (42 lines)
- engine/api/scene_routes.py (135 lines)
- engine/world/world_routes.py
- tests/test_routes.py
- tests/test_shop.py
- tests/test_inventory.py
- tests/test_e2e_player_journey.py
- tests/test_world_state.py

**New Files**
- engine/api/campaign/runtime_commands.py (148 lines) — command dispatch + world tick
- engine/api/campaign/tick_loop.py (137 lines) — async background tick
- tests/test_creation_contract.py (25 tests)
- tests/test_tick_loop.py (10 tests)
- tests/test_websocket_runtime.py (6 tests)
- tests/test_dialog_kernel_bridge.py (8 tests)
- tests/test_kernel_bridges.py (14 tests)
- tests/test_no_legacy_imports.py (2 tests)

**Remaining Opportunities**
- Load NPC-specific DialogDefs from data JSON files (currently generates defaults).
- Wire tick event push to actually send granular diffs instead of full snapshots.
- Add end-to-end integration test covering full flow: creation → WS → tick → save → load → reconnect.
