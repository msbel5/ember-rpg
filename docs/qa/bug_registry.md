# Bug Registry

## Scope
- Audit date: 2026-03-28
- Phase opened: Pre-phase reality audit
- Severity guide:
  - `P0`: blocks launch, onboarding, commands, save/load, or causes crash/desync
  - `P1`: major demo blocker or invalid QA evidence
  - `P2`: polish or secondary flow issue

| ID | Severity | Summary | Repro Steps | Status | Fix Commit | Visual Evidence |
|----|----------|---------|-------------|--------|------------|-----------------|
| BUG-001 | P1 | Desktop automation scenarios report `pass` while still capturing the title screen instead of the expected gameplay or save-panel state. | 1. Run `python -m automation.runner --executor win32_desktop --scenario C:\Users\msbel\projects\ember-rpg\godot-client\tests\automation\scenarios\save_panel_smoke.toml` 2. Open `open_save_panel.png` 3. Observe the title screen instead of the in-session save/load panel. Repeat with `world_click_smoke.toml`. | Open |  | `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\save_panel_smoke\20260328T024538Z\os_screens\open_save_panel.png`; `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\world_click_smoke\20260328T024553Z\os_screens\click_world_target.png` |
| BUG-002 | P1 | Resume automation is driving the wrong player state. The continue browser opens with `Fallback`, finds no saves, and later corrupts the player field into `look aroundFallback`, surfacing `HTTP 400`. | 1. Run `python -m automation.runner --executor win32_desktop --scenario C:\Users\msbel\projects\ember-rpg\godot-client\tests\automation\scenarios\resume_and_command.toml` 2. Open the OS screenshots 3. Observe `Resume Campaign` with `Fallback` and `No saves found for this player`, followed by `Backend error: HTTP 400`. | Open |  | `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\resume_and_command\20260328T024519Z\os_screens\open_continue.png`; `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\resume_and_command\20260328T024519Z\os_screens\load_first_save.png`; `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\resume_and_command\20260328T024519Z\os_screens\submit_command.png` |
| BUG-003 | P2 | The keyboard-first new-game automation does not advance past the title shell even though the report marks the run as successful. | 1. Run `python -m automation.runner --executor win32_desktop --scenario C:\Users\msbel\projects\ember-rpg\godot-client\tests\automation\scenarios\new_game_keyboard_flow.toml` 2. Open `advance_identity.png` 3. Observe the title screen rather than the identity or questionnaire step. | Open |  | `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\new_game_keyboard_flow\20260328T024442Z\os_screens\advance_identity.png` |

## Notes
- These are QA-harness bugs first, not confirmed product regressions. They still block honest Director Mode signoff because they produce false-positive visual evidence.
