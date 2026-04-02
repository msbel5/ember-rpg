# Visual Automation Report: dialog_interaction_desktop

- Executor: `win32_desktop`
- Started: `2026-04-02T14:59:19.453895+00:00`
- Finished: `2026-04-02T15:00:02.771082+00:00`
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
- `move_to_dialog_npc`
- `send_move_to_dialog_npc`
- `wait_for_move_history`
- `wait_for_move_unlock`
- `wait_for_talk_action`
- `send_talk`
- `wait_for_dialog`
- `wait_for_dialog_npc_name`
- `remember_dialog_text`
- `choose_first_dialog_option`
- `wait_for_dialog_followup`
- `close_dialog`
- `wait_for_dialog_hidden`

## Capability Gaps
- none

## Issues
- none

## Artifacts
- `os_screenshot` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\focus_window.png`
- `viewport_capture` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\focus_window.png` (TitleScreen)
- `os_screenshot` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\open_continue.png`
- `viewport_capture` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\open_continue.png` (TitleScreen)
- `os_screenshot` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\load_first_save.png`
- `viewport_capture` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\load_first_save.png` (GameSession)
- `os_screenshot` `send_talk`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\send_talk.png`
- `viewport_capture` `send_talk`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\send_talk.png` (GameSession)
- `os_screenshot` `choose_first_dialog_option`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\choose_first_dialog_option.png`
- `viewport_capture` `choose_first_dialog_option`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\choose_first_dialog_option.png` (GameSession)
- `os_screenshot` `wait_for_dialog_hidden`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\os_screens\wait_for_dialog_hidden.png`
- `viewport_capture` `wait_for_dialog_hidden`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\dialog_interaction_desktop\20260402T145919Z\viewport_captures\wait_for_dialog_hidden.png` (GameSession)

## Notes
- Automation selected backend `http://127.0.0.1:8766` because `http://127.0.0.1:8741` did not satisfy the campaign contract.
- Prepared canonical campaign save fixture `auto_dialog_interaction_desktop_dialogsmoke` for player `DialogSmoke`.
