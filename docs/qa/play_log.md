# Play Log

## Scope
- Date opened: 2026-03-28
- Current-cycle evidence source:
  - `godot-client/tests/manual/campaign_visual_driver.py`
  - visual probe manifests under `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/`
- Note:
  - the driver executes each command turn-by-turn
  - milestone screenshots are captured every `10` turns for long-form runs
  - the rows below record the audited milestone turns used for signoff, while the full command sequence remains in each run's `manifest.md` and `play_log_rows.md`

## Suite Status
- Targeted backend suite: `28 passed`
- Backend chaos suite: `4 passed`
- Godot headless preflight: green

| Turn | Command | Expected | Actual | Bug? | Screenshot |
|------|---------|----------|--------|------|------------|
| 0 | `new flow -> fantasy_ember` | Keyboard-driven wizard should reach live gameplay through summary activation. | Fresh current-cycle fantasy new-game pass booted directly into gameplay. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/os_screens/campaign_boot.png` |
| 5 | `move south` | Early post-create gameplay should accept commands and move the player. | Fantasy new-game pass accepted the command and stayed stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/os_screens/command_005.png` |
| 0 | `new flow -> scifi_frontier` | Sci-fi wizard should also reach live gameplay through summary activation. | Fresh current-cycle sci-fi new-game pass booted directly into gameplay. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/os_screens/campaign_boot.png` |
| 5 | `move south` | Early post-create gameplay should accept commands and move the player. | Sci-fi new-game pass accepted the command and stayed stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/os_screens/command_005.png` |
| 10 | `build workshop` | Continue flow should remain stable through settlement commands. | Fantasy `50`-turn run stayed in the live shell with updated orders and narrative. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_010.png` |
| 20 | `assign VisualFantasy to scouting` | Assignment command should resolve without UI drift. | Fantasy `50`-turn run stayed coherent and readable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_020.png` |
| 30 | `move east` | Map movement should remain stable mid-run. | Fantasy `50`-turn run remained stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_030.png` |
| 40 | `look around` | Late-mid run command should update narrative and shell without breaking focus. | Fantasy `50`-turn run remained stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_040.png` |
| 50 | `designate harvest` | End of fantasy short long-form pass should still be stable. | Fantasy `50`-turn run ended green and quick-saved cleanly. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_050.png` |
| 10 | `build workshop` | Continue flow should remain stable through settlement commands. | Sci-fi `50`-turn run stayed in the live shell with updated orders and narrative. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_010.png` |
| 20 | `assign VisualScifi to scouting` | Assignment command should resolve without UI drift. | Sci-fi `50`-turn run stayed coherent and readable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_020.png` |
| 30 | `move east` | Map movement should remain stable mid-run. | Sci-fi `50`-turn run remained stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_030.png` |
| 40 | `look around` | Late-mid run command should update narrative and shell without breaking focus. | Sci-fi `50`-turn run remained stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_040.png` |
| 50 | `designate harvest` | End of sci-fi short long-form pass should still be stable. | Sci-fi `50`-turn run ended green and quick-saved cleanly. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_050.png` |
| 10 | `build workshop` | Fantasy `100`-turn run should remain visually stable beyond smoke length. | The build stayed readable and coherent. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_010.png` |
| 20 | `assign VisualFantasy100 to scouting` | Command flow should still work under longer play. | Orders updated cleanly. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_020.png` |
| 30 | `move east` | Movement should remain stable. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_030.png` |
| 40 | `look around` | Narrative layer should still stay readable. | Stable; no raw token leak. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_040.png` |
| 50 | `designate harvest` | Mid-run harvest command should keep the shell coherent. | Stable; no UI break. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_050.png` |
| 60 | `defend` | Later run should preserve focus actions and status alignment. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_060.png` |
| 70 | `move south` | Player movement should stay synced late in the run. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_070.png` |
| 80 | `inventory` | Inventory access should not desync the shell. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_080.png` |
| 90 | `travel` | Late-run transition command should keep the session alive. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_090.png` |
| 100 | `set stockpile supplies` | End of fantasy `100`-turn run should still present a coherent shell and readable narrative block. | Stable; previous tail-fragment clipping did not reproduce. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_100.png` |
| 10 | `build workshop` | Sci-fi `100`-turn run should remain visually stable beyond smoke length. | The build stayed readable and coherent. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_010.png` |
| 20 | `assign VisualScifi100 to scouting` | Command flow should still work under longer play. | Orders updated cleanly. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_020.png` |
| 30 | `move east` | Movement should remain stable. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_030.png` |
| 40 | `look around` | Narrative layer should still stay readable. | Stable; no raw token leak. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_040.png` |
| 50 | `designate harvest` | Mid-run harvest command should keep the shell coherent. | Stable; no UI break. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_050.png` |
| 60 | `defend` | Later run should preserve focus actions and status alignment. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_060.png` |
| 70 | `move south` | Player movement should stay synced late in the run. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_070.png` |
| 80 | `inventory` | Inventory access should not desync the shell. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_080.png` |
| 90 | `travel` | Late-run transition command should keep the session alive. | Stable. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_090.png` |
| 100 | `set stockpile supplies` | End of sci-fi `100`-turn run should still present a coherent shell and readable narrative block. | Stable; previous tail-fragment clipping did not reproduce. | No | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_100.png` |

## Honest Read
- The build now has real current-cycle `50`-turn and `100`-turn desktop evidence for both adapters.
- No reproduced `P0` or `P1` blocker appeared in the current-cycle wizard, continue, or long-form milestone frames.
- The remaining weakness is quality, not basic stability: the world is still sparse, and the narrative layer still has some awkward phrasing even though the clipping bug is closed.
