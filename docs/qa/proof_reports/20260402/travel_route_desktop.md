# Visual Automation Report: travel_route_desktop

- Executor: `win32_desktop`
- Started: `2026-04-02T15:00:03.170105+00:00`
- Finished: `2026-04-02T15:00:22.802746+00:00`
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
- `open_map_tab`
- `wait_for_route_button`
- `wait_for_route_button_text`
- `use_first_route`
- `wait_for_travel_history`
- `wait_for_travel_arrival`

## Capability Gaps
- none

## Issues
- none

## Artifacts
- `os_screenshot` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\focus_window.png`
- `viewport_capture` `focus_window`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\focus_window.png` (TitleScreen)
- `os_screenshot` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\open_continue.png`
- `viewport_capture` `open_continue`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\open_continue.png` (TitleScreen)
- `os_screenshot` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\load_first_save.png`
- `viewport_capture` `load_first_save`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\load_first_save.png` (GameSession)
- `os_screenshot` `open_map_tab`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\open_map_tab.png`
- `viewport_capture` `open_map_tab`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\open_map_tab.png` (GameSession)
- `os_screenshot` `use_first_route`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\use_first_route.png`
- `viewport_capture` `use_first_route`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\use_first_route.png` (GameSession)
- `os_screenshot` `wait_for_travel_arrival`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\os_screens\wait_for_travel_arrival.png`
- `viewport_capture` `wait_for_travel_arrival`: `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\travel_route_desktop\20260402T150003Z\viewport_captures\wait_for_travel_arrival.png` (GameSession)

## Notes
- Automation selected backend `http://127.0.0.1:8766` because `http://127.0.0.1:8741` did not satisfy the campaign contract.
- Prepared canonical campaign save fixture `auto_travel_route_desktop_travelsmoke` for player `TravelSmoke`.
