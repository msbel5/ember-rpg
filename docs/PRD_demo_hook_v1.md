# PRD: Demo Hook v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Demo Hook` from `3` to `5` in the first pass by making the first five minutes feel intentional, curious, and player-directed. This pass focuses on onboarding, first-scene framing, and immediate reasons to interact.

## 2. Scope
- In scope: title promise, wizard payoff, first-scene callouts, quest or settlement nudges, and the first readable curiosity loop in gameplay.
- Out of scope: full narrative arcs, large quest expansions, or new systemic content families.

## 3. Functional Requirements
FR-01: The title and onboarding SHALL communicate a stronger fantasy than `Choose Your Adventure`.
FR-02: The creation summary and first gameplay state SHALL clearly answer `why should I care` and `what can I do next`.
FR-03: The initial gameplay shell SHALL surface at least one nearby curiosity and one actionable next step without requiring prior system knowledge.
FR-04: Adapter flavor SHALL be visible in the first minute for both `fantasy_ember` and `scifi_frontier`.

## 4. Data Structures
```python
class HookCue(TypedDict):
    source: str
    text: str
    priority: int
```

## 5. Public API
No external API change.
Internal implementation MAY add hook cue formatting or summary callouts inside existing client and backend surfaces.

## 6. Acceptance Criteria
AC-01 [FR-01]: Fresh title and wizard screenshots communicate a stronger premise than the baseline shell.
AC-02 [FR-02]: After finalize or resume, the player can identify at least one meaningful next action without opening documentation.
AC-03 [FR-03]: Narrative, quest, settlement, or world cues expose a nearby point of interest in the first gameplay screen.
AC-04 [FR-04]: The two adapters do not feel like the same scene with recolored labels.

## 7. Performance Requirements
- Hook cues SHALL appear immediately on first playable frame or first narrative update.

## 8. Error Handling
- If richer hook cues are unavailable, the fallback still points the player toward a concrete next action.

## 9. Integration Points
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/narrative_panel.gd`
- `godot-client/scripts/ui/quest_panel.gd`
- `godot-client/scripts/ui/settlement_panel.gd`
- `frp-backend/engine/api/campaign_runtime.py`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless or backend coverage for first-scene hook copy and cue presence where practical, then confirm with live GUI evidence.

## Changelog
- 2026-03-28: Initial Director Mode demo-hook recovery PRD.
