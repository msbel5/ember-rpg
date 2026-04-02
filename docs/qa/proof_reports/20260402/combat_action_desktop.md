# Visual Automation Report: combat_action_desktop

- Executor: `win32_desktop`
- Started: `2026-04-02T15:00:23.185235+00:00`
- Finished: `2026-04-02T15:00:57.251205+00:00`
- Status: `pass`
- Success: `yes`

## Steps
- `focus_window`
- `wait_for_continue_button`
- `open_continue`
- `set_player_lookup`
- `wait_for_load_button`
- `load_first_save`
- `wait_for_game_session`
- `wait_for_command_input`
- `wait_for_shell_unlock`
- `prepare_attack`
- `enter_combat`
- `wait_for_attack_history`
- `wait_for_combat_panel`
- `wait_for_combat_round`
- `use_disengage`
- `wait_for_disengage_history`

## Capability Gaps
- none

## Issues
- none

## Artifacts
- `os_screenshot` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\os_screens\focus_window.png`
- `viewport_capture` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\viewport_captures\focus_window.png` (TitleScreen)
- `os_screenshot` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\os_screens\open_continue.png`
- `viewport_capture` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\viewport_captures\open_continue.png` (TitleScreen)
- `os_screenshot` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\os_screens\load_first_save.png`
- `viewport_capture` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\viewport_captures\load_first_save.png` (GameSession)
- `os_screenshot` `enter_combat`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\os_screens\enter_combat.png`
- `viewport_capture` `enter_combat`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\viewport_captures\enter_combat.png` (GameSession)
- `os_screenshot` `use_disengage`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\os_screens\use_disengage.png`
- `viewport_capture` `use_disengage`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\combat_action_desktop\20260402T150023Z\viewport_captures\use_disengage.png` (GameSession)

## Notes
- Automation selected backend `http://127.0.0.1:8766` because `http://127.0.0.1:8741` did not satisfy the campaign contract.
- Prepared canonical campaign save fixture `auto_combat_action_desktop_combatsmoke` for player `CombatSmoke`.
