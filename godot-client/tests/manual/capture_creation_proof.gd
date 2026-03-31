extends SceneTree

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")


func _initialize() -> void:
	var title_scene = load("res://scenes/title_screen.tscn")
	if title_scene == null:
		push_error("Failed to load title screen scene.")
		quit(1)
		return

	var title_instance = title_scene.instantiate()
	root.add_child(title_instance)
	await process_frame
	await process_frame

	var title_paths: Array[String] = []
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "00_title"))

	title_instance._on_new_game()
	await process_frame
	await process_frame
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "01_identity"))

	title_instance._apply_creation_state({
		"creation_id": "proof_create_1",
		"player_name": "VisualSmoke",
		"adapter_id": "fantasy_ember",
		"profile_id": "standard",
		"seed": 42,
		"question_groups": [
			{
				"id": "setting_scale",
				"title": "Setting & Scale",
				"subtitle": "Decide what kind of frontier this commander is walking into.",
				"questions": [
					{
						"id": "q_world_frame",
						"text": "What kind of frontier is collapsing first?",
						"answers": [
							{"id": "a_rural", "text": "A brittle border hamlet", "world_tags": ["frontier hunger"], "tone_tags": ["low fantasy"], "quest_themes": ["bandit pressure"]},
							{"id": "a_arcane", "text": "A scholar enclave under strain", "world_tags": ["arcane debt"], "tone_tags": ["occult pressure"], "quest_themes": ["knowledge theft"]},
						],
					},
				],
			},
			{
				"id": "values_pressure",
				"title": "Values / Pressure / Trauma",
				"subtitle": "Define what the commander protects first.",
				"questions": [
					{
						"id": "q_pressure",
						"text": "Which wound still shapes the commander's judgment?",
						"answers": [
							{"id": "a_watch", "text": "Failure on the wall", "world_tags": ["security panic"], "tone_tags": ["hard duty"], "quest_themes": ["guard shortages"]},
							{"id": "a_hunger", "text": "A season of hunger", "world_tags": ["ration fear"], "tone_tags": ["grim scarcity"], "quest_themes": ["food pressure"]},
						],
					},
				],
			},
		],
		"answers": [
			{"question_id": "q_world_frame", "answer_id": "a_arcane"},
			{"question_id": "q_pressure", "answer_id": "a_hunger"},
		],
		"current_roll": [16, 15, 13, 12, 10, 8],
		"saved_roll": [15, 14, 12, 11, 10, 8],
		"recommended_class": "mage",
		"recommended_alignment": "CG",
		"recommended_skills": ["arcana", "history", "insight"],
		"campaign_genesis": {
			"world_premise": "A scholar enclave on the edge of starvation is trying to stay useful before its rivals strip it for parts.",
			"commander_profile": "A learned field commander trusted for hard triage, soft diplomacy, and painful compromise.",
			"starting_pressure": "Food ledgers are collapsing while the guard insists every scrap belongs on the walls.",
			"quest_seed_themes": ["food pressure", "knowledge theft", "guard shortages"],
		},
		"world_seed_hints": {
			"tone": ["grim scarcity", "occult pressure"],
			"world_tags": ["arcane debt", "ration fear"],
		},
	})
	title_instance._go_to_step(title_instance.STEP_QUESTIONNAIRE)
	await process_frame
	await process_frame
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "02_questionnaire"))

	title_instance._go_to_step(title_instance.STEP_ROLL)
	await process_frame
	await process_frame
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "03_roll"))

	title_instance._go_to_step(title_instance.STEP_BUILD)
	await process_frame
	await process_frame
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "04_build"))

	title_instance._go_to_step(title_instance.STEP_SUMMARY)
	await process_frame
	await process_frame
	title_paths.append(ScreenshotCapture.capture_viewport(root, "phase2/title_proof", "05_summary"))

	for path in title_paths:
		if not path.is_empty():
			print(path)
	quit(0)
