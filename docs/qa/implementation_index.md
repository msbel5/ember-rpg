# Implementation Index

## Scope
- Audit date: 2026-03-28
- Note: `TodoWrite` is not available in this session. Active task tracking is being handled with `update_plan`, and completed work is mirrored here immediately.

| File | What Changed | Why | Phase | Test |
|------|--------------|-----|-------|------|
| `docs/qa/vqr_scorecard.md` | Created the Director Mode baseline VQR ledger with evidence-backed scores and rationale. | The current cycle needs a canonical before/after score history before any implementation work. | Pre-phase reality audit | Targeted backend suite; backend chaos suite; automation Python suite; Godot headless preflight; automation bridge; fresh desktop captures |
| `docs/qa/bug_registry.md` | Created the Director Mode bug ledger and logged the reproduced visual automation false positives. | The audit already found QA-blocking bugs that must not be lost between phases. | Pre-phase reality audit | `python -m automation.runner --executor win32_desktop --scenario ...` for `new_game_keyboard_flow`, `resume_and_command`, `save_panel_smoke`, and `world_click_smoke` |
| `docs/qa/implementation_index.md` | Created the implementation ledger. | The brief requires a file-level index so the team can see exactly what changed and why. | Pre-phase reality audit | Manual audit |
| `docs/qa/play_log.md` | Created the visual-play ledger scaffold and recorded the initial graphical boot observation. | The current cycle needs a single running play record before 50-turn adapter passes begin. | Pre-phase reality audit | Fresh graphical title boot and desktop screenshot |
| `docs/qa/demo_signoff_matrix.md` | Rewrote overstated visual and long-form gates from green to partial/open where current-cycle evidence does not support closure. | The existing signoff file was too optimistic for Director Mode and relied on stale or non-visual proof. | Pre-phase reality audit | Fresh desktop captures; automation runner audit; existing 2026-03-28 screenshots; mandatory suites |
| `docs/PRD_silhouette_distinctiveness_v1.md` | Added the silhouette recovery PRD with existing-asset-first rendering targets. | `SD 2` is below demo floor and needs a bounded implementation brief. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_tile_texture_depth_v1.md` | Added the tile-depth recovery PRD for terrain readability and placeholder honesty. | The world still reads like repeated wallpaper rather than an authored place. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_atmospheric_density_v1.md` | Added the atmosphere recovery PRD for title and gameplay mood layers. | `AD 1` is one of the weakest parts of the current build. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_interaction_feedback_v1.md` | Added the interaction-feedback PRD for click acknowledgement and visible busy states. | The world still responds mostly through text, not visual confirmation. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_narrative_presentation_v1.md` | Added the narrative-presentation PRD for copy cleanup and stronger player-facing voice. | Current text reports state but does not create curiosity. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_animation_fluidity_v1.md` | Added the animation-fluidity PRD for movement lerp and lightweight motion. | `AF 1` is a core reason the game feels like a data structure instead of a place. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_ui_polish_v1.md` | Added the UI-polish PRD for title, wizard, and shell theming. | `UP 2` is below demo bar and immediately visible on first boot. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
| `docs/PRD_demo_hook_v1.md` | Added the demo-hook PRD for first-five-minute curiosity and first-scene direction. | The baseline build still fails the “why keep playing” test. | Phase 1 PRD writing | Manual audit and baseline VQR scorecard |
