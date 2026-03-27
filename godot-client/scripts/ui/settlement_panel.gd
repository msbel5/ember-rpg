extends PanelContainer
class_name SettlementPanelWidget

signal command_requested(command_text: String)

@onready var summary_label: Label = $SettlementMargin/SettlementVBox/SummaryLabel
@onready var defend_button: Button = $SettlementMargin/SettlementVBox/QuickActions/DefendButton
@onready var harvest_button: Button = $SettlementMargin/SettlementVBox/QuickActions/HarvestButton
@onready var build_button: Button = $SettlementMargin/SettlementVBox/QuickActions/BuildButton
@onready var detail_log: RichTextLabel = $SettlementMargin/SettlementVBox/DetailLog

var _is_waiting: bool = false


func _ready() -> void:
	defend_button.pressed.connect(func() -> void:
		command_requested.emit("defend")
	)
	harvest_button.pressed.connect(func() -> void:
		command_requested.emit("designate harvest")
	)
	build_button.pressed.connect(func() -> void:
		command_requested.emit("build house")
	)
	GameState.state_updated.connect(_refresh)
	GameState.settlement_updated.connect(_on_settlement_updated)
	_refresh()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	defend_button.disabled = waiting
	harvest_button.disabled = waiting
	build_button.disabled = waiting


func _on_settlement_updated(_settlement: Dictionary) -> void:
	_refresh()


func _refresh() -> void:
	var settlement = GameState.settlement_state
	if settlement.is_empty():
		summary_label.text = "No active settlement"
		detail_log.clear()
		detail_log.append_text("Campaign settlement data will appear here.")
		set_waiting(_is_waiting)
		return

	var residents: Array = settlement.get("residents", [])
	var jobs: Array = settlement.get("jobs", [])
	var alerts: Array = settlement.get("alerts", [])
	var stockpiles: Array = settlement.get("stockpiles", [])
	summary_label.text = "%s  |  Pop %d  |  %s" % [
		str(settlement.get("name", "Settlement")),
		int(settlement.get("population", residents.size())),
		str(settlement.get("defense_posture", "normal")).capitalize(),
	]

	detail_log.clear()
	_append_section("Residents", _resident_lines(residents))
	_append_section("Jobs", _job_lines(jobs))
	_append_section("Stockpiles", _stockpile_lines(stockpiles))
	_append_section("Alerts", _alert_lines(alerts))
	set_waiting(_is_waiting)


func _append_section(title: String, lines: Array[String]) -> void:
	detail_log.append_text("[b]%s[/b]\n" % title)
	if lines.is_empty():
		detail_log.append_text("None\n\n")
		return
	for line in lines.slice(0, 6):
		detail_log.append_text("- %s\n" % line)
	detail_log.append_text("\n")


func _resident_lines(residents: Array) -> Array[String]:
	var lines: Array[String] = []
	for resident in residents:
		if not (resident is Dictionary):
			continue
		lines.append("%s: %s (%s)" % [
			str(resident.get("name", "Resident")),
			str(resident.get("assignment", resident.get("role", "idle"))),
			str(resident.get("mood", "steady")),
		])
	return lines


func _job_lines(jobs: Array) -> Array[String]:
	var lines: Array[String] = []
	for job in jobs:
		if not (job is Dictionary):
			continue
		lines.append("%s [%s]" % [
			str(job.get("kind", "job")).capitalize(),
			str(job.get("status", "queued")),
		])
	return lines


func _stockpile_lines(stockpiles: Array) -> Array[String]:
	var lines: Array[String] = []
	for stockpile in stockpiles:
		if not (stockpile is Dictionary):
			continue
		var tags = stockpile.get("resource_tags", [])
		lines.append("%s (%s)" % [
			str(stockpile.get("label", "Stockpile")),
			", ".join(tags) if tags is Array else "",
		])
	return lines


func _alert_lines(alerts: Array) -> Array[String]:
	var lines: Array[String] = []
	for alert in alerts:
		lines.append(str(alert))
	return lines
