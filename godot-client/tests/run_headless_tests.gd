extends SceneTree

const BackendProbe = preload("res://tests/doubles/backend_probe.gd")
const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")
const ResponseNormalizer = preload("res://scripts/net/response_normalizer.gd")
const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const TilemapController = preload("res://scripts/world/tilemap_controller.gd")
const CameraController = preload("res://scripts/world/camera_controller.gd")
const EntityLayer = preload("res://scripts/world/entity_layer.gd")
const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")

var failures: int = 0


func _initialize() -> void:
	await _run_tests()
	if failures == 0:
		print("All Godot headless tests passed.")
	quit(failures)


func _run_tests() -> void:
	_test_backend_routes()
	_test_campaign_backend_routes()
	_test_response_normalizer()
	_test_game_state_normalization()
	await _test_scene_instantiation()
	await _test_world_shell()
	await _test_entity_rendering()
	await _test_ui_panels()
	_test_generated_asset_resolution()
	_test_asset_bootstrap()
	await _cleanup_test_nodes()


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)


func _game_state() -> Node:
	return root.get_node_or_null("GameState")


func _test_backend_routes() -> void:
	var probe = BackendProbe.new()
	var noop := func(_data = null) -> void:
		pass
	var backend_script = load("res://autoloads/backend.gd")
	var backend_instance = backend_script.new()
	_assert_true(not String(backend_instance._resolve_base_url()).strip_edges().is_empty(), "Backend resolves a usable default base URL")
	backend_instance.free()

	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available")
	if game_state == null:
		return
	game_state.reset()
	game_state.player = {"name": "Chaos"}

	probe.load_game("slot_a", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/session/load/slot_a", "load_game uses session load route")

	probe.list_saves(noop)
	_assert_true(probe.last_request.get("path", "") == "/game/saves/Chaos", "list_saves uses player-scoped route")

	probe.get_inventory("session_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/session/session_1/inventory", "get_inventory uses inventory route")

	probe.save_game("session_1", noop, "campfire", "Chaos")
	var save_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/session/session_1/save", "save_game uses session save route")
	_assert_true(save_body is Dictionary and save_body.get("player_id", "") == "Chaos", "save_game sends player_id")
	_assert_true(save_body is Dictionary and save_body.get("slot_name", "") == "campfire", "save_game sends optional slot_name")

	probe.delete_save("campfire", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/saves/campfire", "delete_save uses the save delete route")
	probe.free()


func _test_campaign_backend_routes() -> void:
	var probe = BackendProbe.new()
	var noop := func(_data = null) -> void:
		pass

	probe.start_campaign_creation("Chaos", "fantasy_ember", noop, "standard", 42, "Harbor Town")
	var creation_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/start", "start_campaign_creation uses the campaign creation start route")
	_assert_true(creation_body is Dictionary and creation_body.get("adapter_id", "") == "fantasy_ember", "start_campaign_creation sends adapter_id")
	_assert_true(creation_body is Dictionary and int(creation_body.get("seed", -1)) == 42, "start_campaign_creation sends the requested seed")

	probe.answer_campaign_creation("create_1", "q_intro", "a_1", noop)
	var answer_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/create_1/answer", "answer_campaign_creation uses the answer route")
	_assert_true(answer_body is Dictionary and answer_body.get("question_id", "") == "q_intro", "answer_campaign_creation sends question_id")

	probe.reroll_campaign_creation("create_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/create_1/reroll", "reroll_campaign_creation uses the reroll route")

	probe.save_campaign_creation_roll("create_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/create_1/save-roll", "save_campaign_creation_roll uses the save-roll route")

	probe.swap_campaign_creation_roll("create_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/create_1/swap-roll", "swap_campaign_creation_roll uses the swap-roll route")

	probe.finalize_campaign_creation("create_1", noop, {"player_class": "mage"})
	var finalize_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/creation/create_1/finalize", "finalize_campaign_creation uses the finalize route")
	_assert_true(finalize_body is Dictionary and finalize_body.get("player_class", "") == "mage", "finalize_campaign_creation sends override payload")

	probe.create_campaign("Chaos", "warrior", "fantasy_ember", noop, "standard", 42)
	var create_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns", "create_campaign uses the campaign creation route")
	_assert_true(create_body is Dictionary and create_body.get("adapter_id", "") == "fantasy_ember", "create_campaign sends adapter_id")
	_assert_true(create_body is Dictionary and int(create_body.get("seed", -1)) == 42, "create_campaign sends an explicit seed")

	probe.get_campaign("camp_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1", "get_campaign uses the campaign snapshot route")

	probe.submit_campaign_command("camp_1", "look around", noop, "assign", {"resident": "Iris", "job": "hauling"})
	var command_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1/commands", "submit_campaign_command uses the campaign command route")
	_assert_true(command_body is Dictionary and command_body.get("shortcut", "") == "assign", "submit_campaign_command sends shortcut metadata")

	probe.get_campaign_region("camp_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1/region/current", "get_campaign_region uses the realized region route")

	probe.get_campaign_settlement("camp_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1/settlement/current", "get_campaign_settlement uses the settlement route")

	probe.save_campaign("camp_1", noop, "frontier", "Chaos")
	var save_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1/save", "save_campaign uses the campaign save route")
	_assert_true(save_body is Dictionary and save_body.get("slot_name", "") == "frontier", "save_campaign sends slot_name")

	probe.list_campaign_saves("camp_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1/saves", "list_campaign_saves uses the campaign save listing route")

	probe.load_campaign("frontier", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/load/frontier", "load_campaign uses the campaign load route")

	probe.delete_campaign("camp_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/campaigns/camp_1", "delete_campaign uses the campaign delete route")
	probe.free()


func _test_game_state_normalization() -> void:
	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available for normalization")
	if game_state == null:
		return
	game_state.reset()
	game_state.update_from_response({
		"creation_id": "create_1",
		"player_name": "Chaos",
		"adapter_id": "fantasy_ember",
		"profile_id": "standard",
		"seed": 42,
		"questions": [{"id": "q1", "text": "Test?", "answers": [{"id": "a1", "text": "Yes"}]}],
		"current_roll": [15, 14, 13, 12, 10, 8],
		"recommended_class": "warrior",
		"recommended_alignment": "LG",
		"recommended_skills": ["athletics", "perception"],
	})
	_assert_true(game_state.creation_state.get("creation_id", "") == "create_1", "GameState stores campaign creation state payloads")
	_assert_true(game_state.adapter_id == "fantasy_ember" and game_state.profile_id == "standard", "GameState tracks adapter/profile from creation state")

	game_state.reset()
	game_state.update_from_response({
		"scene": "combat",
		"combat": {
			"round": 2,
			"active": "Chaos",
			"ended": false,
			"combatants": [],
		},
		"player": {
			"name": "Chaos",
			"position": [7, 8],
			"facing": "east",
			"gold": 12,
			"inventory": [{"id": "bread", "name": "Bread"}],
		},
		"map": {
			"width": 48,
			"height": 48,
			"spawn_point": [5, 5],
		},
		"world_entities": [
			{"id": "guard_1", "entity_type": "npc", "name": "Guard", "position": [2, 3], "disposition": "friendly"},
			{"id": "rat_1", "entity_type": "creature", "name": "Rat", "position": [4, 5], "disposition": "hostile"},
			{"id": "bread_1", "entity_type": "item", "name": "Bread", "position": [6, 7]},
		],
		"ground_items": [{"id": "bread_1", "entity_type": "item"}],
		"active_quests": [{"quest_id": "q1"}],
		"quest_offers": [{"id": "offer_1"}],
	})

	_assert_true(game_state.is_in_combat(), "GameState normalizes combat payload from action response")
	_assert_true(game_state.combat_state.get("round", 0) == 2, "combat_state preserves round")
	_assert_true(game_state.player_map_pos == Vector2i(7, 8), "player position is sourced from backend")
	_assert_true(game_state.player_facing == 1, "player facing is normalized from string")
	_assert_true(int(game_state.map_data.get("width", 0)) == 48, "map payload is normalized into map_data")
	_assert_true(game_state.entities.get("npcs", []).size() == 1, "friendly world entities group as npcs")
	_assert_true(game_state.entities.get("enemies", []).size() == 1, "hostile world entities group as enemies")
	_assert_true(game_state.entities.get("items", []).size() == 1, "item world entities group as items")
	_assert_true(game_state.ground_items.size() == 1, "ground items are retained")
	_assert_true(game_state.active_quests.size() == 1 and game_state.quest_offers.size() == 1, "quest payloads are retained")

	game_state.reset()
	game_state.update_from_response({
		"campaign_id": "camp_1",
		"adapter_id": "fantasy_ember",
		"profile_id": "standard",
		"narrative": "Chaos enters Dragon Eyrie.",
		"campaign": {
			"world": {"adapter_id": "fantasy_ember", "profile_id": "standard"},
			"player": {"name": "Chaos", "position": [9, 9]},
			"scene": "exploration",
			"location": "",
			"map_data": TileCatalog.build_placeholder_map(16, 12),
			"world_entities": [],
			"settlement": {"name": "Dragon Eyrie", "residents": []},
			"recent_event_log": [],
		},
	})
	_assert_true(game_state.has_active_campaign(), "GameState enters campaign runtime when campaign payload arrives")
	_assert_true(game_state.location == "Dragon Eyrie", "GameState falls back to settlement name when campaign location is blank")
	_assert_true(game_state.get_display_location() == "Dragon Eyrie", "display location falls back to settlement name for campaign payloads")


func _test_response_normalizer() -> void:
	var merged_map = ResponseNormalizer.normalize_map({
		"map": {
			"width": 40,
			"height": 40,
		}
	}, {
		"width": 20,
		"tiles": [["grass"]],
	})
	_assert_true(int(merged_map.get("width", 0)) == 40 and merged_map.has("tiles"), "ResponseNormalizer merges map payloads with existing state")

	var normalized_ascii_town_map = ResponseNormalizer.normalize_map({
		"map": {
			"width": 3,
			"height": 2,
			"metadata": {"map_type": "town"},
			"tiles": [
				["#", "=", "."],
				["~", "D", "<"],
			],
		}
	})
	var town_tiles = normalized_ascii_town_map.get("tiles", [])
	_assert_true(
		town_tiles.size() == 2
		and town_tiles[0] is Array
		and town_tiles[1] is Array
		and town_tiles[0][0] == "wall"
		and town_tiles[0][1] == "cobblestone"
		and town_tiles[0][2] == "grass"
		and town_tiles[1][0] == "water"
		and town_tiles[1][1] == "wood_floor"
		and town_tiles[1][2] == "stone_floor",
		"ResponseNormalizer converts backend ASCII town symbols into named terrain tiles"
	)

	var normalized_ascii_dungeon_map = ResponseNormalizer.normalize_map({
		"map": {
			"width": 2,
			"height": 1,
			"metadata": {"map_type": "dungeon"},
			"tiles": [[",", "."]],
		}
	})
	var dungeon_tiles = normalized_ascii_dungeon_map.get("tiles", [])
	_assert_true(
		dungeon_tiles.size() == 1
		and dungeon_tiles[0] is Array
		and dungeon_tiles[0][0] == "stone_floor"
		and dungeon_tiles[0][1] == "stone_floor",
		"ResponseNormalizer uses dungeon-appropriate floor tiles for ASCII maps"
	)

	var normalized_entities = ResponseNormalizer.normalize_entities({
		"world_entities": [
			{"id": "merchant_1", "entity_type": "npc", "name": "Merchant", "position": [1, 2]},
			{"id": "wolf_1", "entity_type": "creature", "name": "Wolf", "position": [2, 3], "disposition": "hostile"},
		]
	})
	_assert_true(normalized_entities.get("npcs", []).size() == 1 and normalized_entities.get("enemies", []).size() == 1, "ResponseNormalizer groups world entities into gameplay buckets")
	_assert_true(ResponseNormalizer.command_requires_inventory_refresh("pick up bread"), "ResponseNormalizer flags inventory-affecting commands")
	_assert_true(not ResponseNormalizer.command_requires_inventory_refresh("look around"), "ResponseNormalizer ignores non-inventory commands")


func _test_scene_instantiation() -> void:
	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available for scenes")
	if game_state == null:
		return
	game_state.reset()

	var title_scene = load("res://scenes/title_screen.tscn")
	_assert_true(title_scene != null, "TitleScreen scene loads")
	if title_scene != null:
		var title_instance = title_scene.instantiate()
		root.add_child(title_instance)
		await process_frame
		_assert_true(is_instance_valid(title_instance), "TitleScreen instantiates")
		title_instance._on_new_game()
		await process_frame
		_assert_true(title_instance.get_node("CharacterCreation").visible, "TitleScreen opens the creation wizard")
		title_instance._apply_creation_state({
			"creation_id": "create_1",
			"player_name": "Chaos",
			"adapter_id": "fantasy_ember",
			"profile_id": "standard",
			"seed": 42,
			"questions": [
				{
					"id": "q_intro",
					"text": "How do you react?",
					"answers": [
						{"id": "a_1", "text": "Stand firm"},
						{"id": "a_2", "text": "Slip away"},
					],
				}
			],
			"answers": [],
			"current_roll": [15, 14, 13, 12, 10, 8],
			"saved_roll": [13, 12, 12, 10, 9, 8],
			"recommended_class": "warrior",
			"recommended_alignment": "LG",
			"recommended_skills": ["athletics", "perception"],
		})
		title_instance._go_to_step(title_instance.STEP_BUILD)
		await process_frame
		var title_class_option = title_instance.get_node("CharacterCreation/VBox/BuildSection/ClassOption")
		var title_alignment_input = title_instance.get_node("CharacterCreation/VBox/BuildSection/AlignmentInput")
		var title_skills_input = title_instance.get_node("CharacterCreation/VBox/BuildSection/SkillsInput")
		var title_mig_input = title_instance.get_node("CharacterCreation/VBox/BuildSection/StatsGrid/MIGInput")
		_assert_true(title_class_option.item_count >= 4, "TitleScreen build step exposes class overrides")
		_assert_true(title_alignment_input.text == "LG", "TitleScreen pre-fills recommended alignment in the build step")
		title_class_option.select(2)
		title_alignment_input.text = "CG"
		title_skills_input.text = "arcana, history"
		title_mig_input.text = "18"
		title_instance._go_to_step(title_instance.STEP_SUMMARY)
		await process_frame
		var title_summary = title_instance.get_node("CharacterCreation/VBox/SummarySection/SummaryText")
		_assert_true(title_summary.text.contains("recommended"), "TitleScreen summary renders creation preview text")
		title_instance._go_to_step(title_instance.STEP_BUILD)
		await process_frame
		_assert_true(str(title_class_option.get_item_metadata(title_class_option.selected)) == "mage", "TitleScreen preserves manual class edits when returning from summary")
		_assert_true(title_alignment_input.text == "CG", "TitleScreen preserves manual alignment edits when returning from summary")
		_assert_true(title_skills_input.text == "arcana, history", "TitleScreen preserves manual skill edits when returning from summary")
		_assert_true(title_mig_input.text == "18", "TitleScreen preserves manual stat edits when returning from summary")
		title_instance.free()
		await process_frame

	var session_scene = load("res://scenes/game_session.tscn")
	_assert_true(session_scene != null, "GameSession scene loads")
	if session_scene != null:
		var session_instance = session_scene.instantiate()
		root.add_child(session_instance)
		await process_frame
		_assert_true(is_instance_valid(session_instance), "GameSession instantiates without session bootstrap")
		_assert_true(session_instance.get_node_or_null("MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer") != null, "GameSession exposes the world viewport container")
		_assert_true(session_instance.get_node_or_null("MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer/WorldViewport/WorldRoot/TerrainLayer") != null, "GameSession exposes a TileMapLayer terrain node")
		_assert_true(session_instance.get_node_or_null("MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer/WorldViewport/WorldRoot/WorldCamera") != null, "GameSession exposes a Camera2D world camera")
		session_instance.free()
		await process_frame


func _test_world_shell() -> void:
	var placeholder_map = TileCatalog.build_placeholder_map(12, 8)
	_assert_true(int(placeholder_map.get("width", 0)) == 12 and placeholder_map.get("tiles", []).size() == 8, "TileCatalog builds placeholder maps")
	_assert_true(TileCatalog.adapter_world_tint("fantasy_ember") != TileCatalog.adapter_world_tint("scifi_frontier"), "TileCatalog exposes adapter-specific world tints")

	var terrain = TilemapController.new()
	root.add_child(terrain)
	await process_frame
	terrain.render_map({})
	_assert_true(terrain.get_used_cells().size() > 0, "TileMapLayer populates placeholder cells")
	terrain.free()
	await process_frame

	var camera = CameraController.new()
	root.add_child(camera)
	await process_frame
	var initial_zoom = camera.zoom
	camera.zoom_in()
	_assert_true(camera.zoom != initial_zoom, "CameraController zoom_in changes zoom")
	for _index in range(16):
		camera.zoom_out()
	_assert_true(camera.get_zoom_index() == 0, "CameraController clamps zoom_out to minimum")
	camera.focus_on_tile(Vector2i(5, 6))
	_assert_true(is_equal_approx(camera.position.x, 88.0) and is_equal_approx(camera.position.y, 104.0), "CameraController centers on the tile midpoint")
	camera.free()
	await process_frame


func _test_entity_rendering() -> void:
	var layer = EntityLayer.new()
	root.add_child(layer)
	await process_frame
	layer.render_entities(Vector2i(4, 4), {
		"npcs": [{"id": "merchant_1", "name": "Merchant", "template": "merchant", "position": [5, 4]}],
		"enemies": [{"id": "wolf_1", "name": "Wolf", "template": "wolf", "position": [6, 4]}],
		"items": [{"id": "bread_1", "name": "Bread", "template": "chest", "position": [7, 4]}],
	})
	_assert_true(layer.get_child_count() == 4, "EntityLayer renders player plus world entities as sprites")
	_assert_true(layer.get_entity_at_tile(Vector2i(5, 4)).get("name", "") == "Merchant", "EntityLayer can look up entities by tile")
	_assert_true(
		EntityLayer.adapter_bucket_tint("player", "fantasy_ember") != EntityLayer.adapter_bucket_tint("player", "scifi_frontier"),
		"EntityLayer exposes adapter-specific sprite tinting"
	)
	layer.free()
	await process_frame

	var session_scene = load("res://scenes/game_session.tscn")
	var session_instance = session_scene.instantiate()
	root.add_child(session_instance)
	await process_frame
	var session_world_view = session_instance.get_node("MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer")
	_assert_true(session_world_view.command_for_entity({"bucket": "npc", "name": "Merchant"}) == "talk merchant", "World view synthesizes talk commands for npc clicks")
	_assert_true(session_world_view.command_for_entity({"bucket": "enemy", "name": "Wolf"}) == "attack wolf", "World view synthesizes attack commands for enemy clicks")
	_assert_true(session_world_view.command_for_entity({"bucket": "item", "name": "Bread"}) == "examine bread", "World view synthesizes examine commands for item clicks")
	session_instance.free()
	await process_frame


func _test_ui_panels() -> void:
	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available for UI panels")
	if game_state == null:
		return
	game_state.reset()
	var session_scene = load("res://scenes/game_session.tscn")
	var session_instance = session_scene.instantiate()
	root.add_child(session_instance)
	await process_frame

	game_state.update_from_response({
		"player": {
			"name": "Chaos",
			"level": 3,
			"classes": {"warrior": 3},
			"hp": 18,
			"max_hp": 20,
			"spell_points": 5,
			"max_spell_points": 8,
			"ap": {"current": 3, "max": 4},
			"xp": 45,
			"gold": 12,
		},
		"character_sheet": {
			"name": "Chaos",
			"class_name": "Warrior",
			"alignment": "LG",
			"stats": [
				{"id": "MIG", "value": 16, "modifier": 3},
				{"id": "AGI", "value": 12, "modifier": 1},
			],
			"skills": [
				{"id": "athletics", "label": "Athletics", "bonus": 5},
				{"id": "perception", "label": "Perception", "bonus": 3},
			],
		},
		"location": "Harbor Town",
		"map_data": TileCatalog.build_placeholder_map(16, 12),
		"items": [{"name": "Bread"}, {"name": "Potion"}],
		"narrative": "You steady your breath in the harbor square.",
	})
	await process_frame
	await process_frame
	for _index in range(20):
		await process_frame

	var player_info = session_instance.get_node("MainMargin/MainVBox/StatusBar/StatusRow/PlayerInfo")
	_assert_true(player_info.text.contains("Chaos"), "Status bar reflects player identity")
	var location_label = session_instance.get_node("MainMargin/MainVBox/StatusBar/StatusRow/LocationLabel")
	_assert_true(location_label.text.contains("Harbor"), "Status bar reflects the current location")

	var inventory_grid = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/InventoryPanel/InventoryMargin/InventoryVBox/ItemGrid")
	_assert_true(inventory_grid.get_child_count() >= 2, "Inventory panel populates grid items")

	var minimap_texture = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/MinimapPanel/MinimapMargin/MinimapVBox/MapTexture")
	_assert_true(minimap_texture.texture != null, "Minimap panel renders a texture from map data")

	var narrative_widget = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/NarrativePanel")
	_assert_true(narrative_widget.get_plain_text().contains("harbor square"), "Narrative panel shows backend narrative")

	var character_panel = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/CharacterPanel/CharacterMargin/CharacterVBox/StatsText")
	_assert_true(character_panel.text.contains("MIG"), "Character panel renders visible stat lines")

	var command_bar = session_instance.get_node("MainMargin/MainVBox/CommandBar")
	command_bar.submit_command("inventory")
	await process_frame
	var history_label = session_instance.get_node("MainMargin/MainVBox/CommandBar/CommandVBox/HistoryLabel")
	_assert_true(history_label.text.contains("inventory"), "Command bar tracks recent commands")
	command_bar.remember_command("move to 7,4")
	await process_frame
	_assert_true(history_label.text.contains("move to 7,4"), "Command bar can record non-textbox commands without duplication")
	var quick_save_button = session_instance.get_node("MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/QuickSaveButton")
	var saves_button = session_instance.get_node("MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/SavesButton")
	_assert_true(quick_save_button != null and saves_button != null, "Command bar exposes save controls")
	command_bar.focus_input()
	await process_frame
	_assert_true(not session_instance._should_focus_command_bar_on_enter(), "GameSession does not swallow Enter when the command bar already has focus")
	quick_save_button.grab_focus()
	await process_frame
	_assert_true(session_instance._should_focus_command_bar_on_enter(), "GameSession focuses the command bar on Enter when input is not focused")

	game_state.update_from_response({
		"scene": "combat",
		"combat": {
			"round": 3,
			"active": "Chaos",
			"ended": false,
			"combatants": [
				{"name": "Chaos", "hp": 18, "max_hp": 20, "ap": 2, "dead": false, "resources": {"movement_remaining": 3, "speed": 6}},
				{"name": "Wolf", "hp": 7, "max_hp": 9, "ap": 2, "dead": false, "resources": {"movement_remaining": 4, "speed": 8}},
			],
		},
		"active_quests": [{"quest_id": "q1", "title": "Bread Run", "status": "active", "deadline": 16}],
		"quest_offers": [{"id": "offer_1", "title": "Clear The Roads", "description": "Drive goblins away.", "reward_gold": 60, "reward_xp": 75}],
		"settlement_state": {
			"name": "Dragon Eyrie",
			"population": 6,
			"defense_posture": "normal",
			"residents": [{"name": "Chaos", "assignment": "command", "role": "commander", "mood": "focused"}],
			"jobs": [{"kind": "forge", "status": "idle"}],
			"stockpiles": [{"label": "Central Stockpile", "resource_tags": ["ore"]}],
			"alerts": ["Raid warning"],
		},
	})
	await process_frame

	var combat_panel = session_instance.get_node("OverlayCanvas/CombatPanel")
	_assert_true(combat_panel.visible, "Combat panel appears when combat state is active")
	var combat_rows = session_instance.get_node("OverlayCanvas/CombatPanel/CombatMargin/CombatVBox/CombatantScroll/CombatantList")
	_assert_true(combat_rows.get_child_count() >= 2, "Combat panel renders combatant rows")

	var active_list = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/QuestPanel/QuestMargin/QuestVBox/QuestScroll/QuestLists/ActiveList")
	var offer_list = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/QuestPanel/QuestMargin/QuestVBox/QuestScroll/QuestLists/OfferList")
	_assert_true(active_list.get_child_count() >= 1 and offer_list.get_child_count() >= 1, "Quest panel renders active and available quest entries")

	var settlement_summary = session_instance.get_node("MainMargin/MainVBox/ContentSplit/Sidebar/SidebarContent/SettlementPanel/SettlementMargin/SettlementVBox/SummaryLabel")
	_assert_true(settlement_summary.text.contains("Dragon Eyrie"), "Settlement panel reflects campaign settlement data")

	var save_load_panel = session_instance.get_node("OverlayCanvas/SaveLoadPanel")
	save_load_panel.open_panel()
	save_load_panel.set_save_summaries([
		{"save_id": "slot_a", "slot_name": "slot_a", "location": "Harbor Town", "timestamp": "2026-03-27T01:02:03"},
	])
	await process_frame
	var save_list = session_instance.get_node("OverlayCanvas/SaveLoadPanel/ModalFrame/ModalMargin/ModalVBox/SaveScroll/SaveList")
	_assert_true(save_list.get_child_count() == 1, "Save/load panel renders save slot summaries")

	session_instance.free()
	await process_frame


func _test_asset_bootstrap() -> void:
	var expected = OS.get_environment("HF_TOKEN").strip_edges()
	if expected.is_empty():
		expected = OS.get_environment("HUGGINGFACE_API_KEY").strip_edges()
	_assert_true(AssetBootstrap.resolve_hf_token() == expected, "AssetBootstrap resolves HF token with fallback")


func _test_generated_asset_resolution() -> void:
	DirAccess.make_dir_recursive_absolute("user://assets/generated/sprites")
	DirAccess.make_dir_recursive_absolute("user://assets/generated/tiles")

	var sprite_image = Image.create(4, 4, false, Image.FORMAT_RGBA8)
	sprite_image.fill(Color(0.9, 0.2, 0.2))
	sprite_image.save_png("user://assets/generated/sprites/cache_test.png")

	var tile_image = Image.create(4, 4, false, Image.FORMAT_RGBA8)
	tile_image.fill(Color(0.2, 0.8, 0.2))
	tile_image.save_png("user://assets/generated/tiles/cache_tile.png")

	var manifest_file = FileAccess.open("user://assets/generated/manifest.json", FileAccess.WRITE)
	manifest_file.store_string(JSON.stringify({
		"sprites": {
			"cache_test": {"relative_path": "sprites/cache_test.png"},
		},
		"tiles": {
			"cache_tile": {"relative_path": "tiles/cache_tile.png"},
		},
	}))
	manifest_file.close()

	_assert_true(AssetBootstrap.resolve_generated_asset("sprites/cache_test.png").begins_with("user://"), "AssetBootstrap prefers user-generated sprite assets")
	_assert_true(AssetManifest.resolve_relative_path("sprites", "cache_test") == "sprites/cache_test.png", "AssetManifest reads generated sprite manifest entries")
	_assert_true(EntitySpriteCatalog.resolve_texture("cache_test") != null, "EntitySpriteCatalog resolves generated textures through manifest data")


func _cleanup_test_nodes() -> void:
	for child in root.get_children():
		if child.name in ["GameState", "Backend"]:
			continue
		child.free()
	await process_frame
