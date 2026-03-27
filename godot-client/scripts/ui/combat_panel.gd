extends PanelContainer
class_name CombatPanelWidget

signal command_requested(command_text: String)

@onready var round_label: Label = $CombatMargin/CombatVBox/HeaderRow/RoundLabel
@onready var active_label: Label = $CombatMargin/CombatVBox/HeaderRow/ActiveLabel
@onready var summary_label: Label = $CombatMargin/CombatVBox/SummaryLabel
@onready var attack_button: Button = $CombatMargin/CombatVBox/QuickActions/AttackButton
@onready var disengage_button: Button = $CombatMargin/CombatVBox/QuickActions/DisengageButton
@onready var inventory_button: Button = $CombatMargin/CombatVBox/QuickActions/InventoryButton
@onready var combatant_list: VBoxContainer = $CombatMargin/CombatVBox/CombatantScroll/CombatantList

var _is_waiting: bool = false


func _ready() -> void:
	attack_button.pressed.connect(_on_attack_pressed)
	disengage_button.pressed.connect(func() -> void:
		command_requested.emit("disengage")
	)
	inventory_button.pressed.connect(func() -> void:
		command_requested.emit("inventory")
	)
	GameState.state_updated.connect(_refresh)
	_refresh()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	_refresh()


func _refresh() -> void:
	if not GameState.is_in_combat():
		visible = false
		_clear_rows()
		return

	visible = true
	var combat_state = GameState.combat_state
	var combatants: Array = combat_state.get("combatants", [])
	round_label.text = "Round %d" % int(combat_state.get("round", 1))
	active_label.text = "Turn: %s" % str(combat_state.get("active", "Unknown"))

	var living_enemies := _living_enemies(combatants)
	summary_label.text = "%d combatant(s), %d hostile target(s)" % [combatants.size(), living_enemies.size()]
	attack_button.disabled = _is_waiting or living_enemies.is_empty()
	disengage_button.disabled = _is_waiting
	inventory_button.disabled = _is_waiting

	_clear_rows()
	for combatant in combatants:
		if not (combatant is Dictionary):
			continue
		combatant_list.add_child(_build_row(combatant))


func _build_row(combatant: Dictionary) -> Control:
	var row = VBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var top_row = HBoxContainer.new()
	var is_player = _is_player_combatant(combatant)
	var is_enemy = not is_player

	var name_label = Label.new()
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.text = str(combatant.get("name", "?"))
	if bool(combatant.get("dead", false)):
		name_label.add_theme_color_override("font_color", Color(0.92, 0.30, 0.30))
	elif is_player:
		name_label.add_theme_color_override("font_color", Color(0.35, 0.92, 0.88))
	top_row.add_child(name_label)

	if is_enemy and not bool(combatant.get("dead", false)):
		var attack_target_button = Button.new()
		attack_target_button.text = "Attack"
		attack_target_button.disabled = _is_waiting
		attack_target_button.pressed.connect(func() -> void:
			command_requested.emit("attack %s" % str(combatant.get("name", "")).to_lower())
		)
		top_row.add_child(attack_target_button)

	row.add_child(top_row)

	var hp_progress = ProgressBar.new()
	hp_progress.max_value = maxi(int(combatant.get("max_hp", 1)), 1)
	hp_progress.value = int(combatant.get("hp", 0))
	hp_progress.show_percentage = false
	hp_progress.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(hp_progress)

	var detail_label = Label.new()
	var resources: Dictionary = combatant.get("resources", {})
	detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail_label.text = "HP %d/%d  AP %d  Move %d/%d" % [
		int(combatant.get("hp", 0)),
		int(combatant.get("max_hp", 1)),
		int(combatant.get("ap", 0)),
		int(resources.get("movement_remaining", 0)),
		int(resources.get("speed", 0)),
	]
	row.add_child(detail_label)

	return row


func _on_attack_pressed() -> void:
	var enemies = _living_enemies(GameState.combat_state.get("combatants", []))
	if enemies.is_empty():
		return
	command_requested.emit("attack %s" % str(enemies[0].get("name", "")).to_lower())


func _living_enemies(combatants: Array) -> Array:
	var enemies: Array = []
	for combatant in combatants:
		if not (combatant is Dictionary):
			continue
		if _is_player_combatant(combatant):
			continue
		if bool(combatant.get("dead", false)):
			continue
		enemies.append(combatant)
	return enemies


func _is_player_combatant(combatant: Dictionary) -> bool:
	return str(combatant.get("name", "")).strip_edges() == str(GameState.player.get("name", "")).strip_edges()


func _clear_rows() -> void:
	for child in combatant_list.get_children():
		child.queue_free()
