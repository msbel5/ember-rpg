---
name: "godot-crpg-shell-authority"
description: "Use when auditing, rewriting, or reviewing Ember RPG's Godot shell, overlays, action bars, dialog, combat, travel, or world readability. Enforces one active owner per UI surface, backend-slice-to-surface clarity, and manual Godot proof before signoff."
---

# Godot CRPG Shell Authority

Use this skill whenever work touches Ember RPG's playable Godot shell:

- `game_session` composition
- title-to-gameplay transition surfaces
- status, dialog, combat, save/load, and action bar ownership
- world readability, labels, silhouettes, and viewport overlays
- dialog, travel, and combat playability proofs

## Core rules

1. One active owner per surface.
   - A feature must not exist both as a scene-instanced surface and a programmatically inserted widget.
   - Applies to status, combat, dialog, save/load, and any other persistent shell surface.
2. The backend owns truth.
   - Godot renders and explains backend state.
   - UI must not invent competing summaries from overlapping payload slices.
3. No inert interaction.
   - Every visible action button must resolve to a real command path.
   - If the interaction is not implemented, hide it or replace it with a truthful empty state.
4. Manual Godot is the primary truth lane.
   - Headless and semantic desktop automation are support lanes, not the final authority.
5. Readability beats debug density.
   - Prefer one clear status signal over three duplicated summaries.
   - Prefer one readable overlay over two partially correct surfaces fighting for space.

## Required workflow

1. Inventory shell owners before editing.
   - Identify the current owner for each surface in the shell.
   - Use `references/backend-slice-to-surface-map.md` and `references/shell-layout-rubric.md`.
2. Remove duplication before adding features.
   - Do not "wire the new surface too" while the old one still renders.
3. Lock the client contract.
   - Confirm which backend slice powers each surface.
   - If UI has to guess, fix the contract or add a narrow additive field.
4. Run the proof ladder.
   - Manual Godot flow from clean reset
   - Headless regression
   - Semantic desktop proof
   - Screenshot readability audit
5. Sign off only after the checklist passes.
   - Use `references/vertical-closure-checklist.md`.

## Anti-patterns

- Scene-instanced and programmatic duplicates of the same feature
- Duplicate HP, location, or combat summaries in different surfaces
- Action bars full of debug fillers or placeholder verbs
- Overlays that cover the viewport and sidebar at the same time
- Labels with no outline, no contrast, or fixed placement that collides with actors
- Renderer-derived "truth" such as guessed combat state or guessed settlement state
- Accepting automation pass results without looking at the actual screenshots

## Surface ownership checklist

For each surface below, exactly one active owner must exist:

- Status strip
- World viewport overlays
- Dialog
- Combat
- Save/load
- Contextual panel
- Bottom action bar

If a second owner exists, remove it before continuing.

## Acceptance gates

### Shell composition

- No duplicate active surfaces
- No overlapping overlays at `1600x900`
- `1280x720` fallback remains bounded and readable

### Interaction honesty

- Every visible verb works
- Dialog, travel, and combat each have one authoritative UI path
- No stale or contradictory state summaries

### Proof

- Manual Godot fresh start proof
- Semantic desktop proof
- Screenshot audit

## Reference files

- Shell layout and ownership rules:
  `references/shell-layout-rubric.md`
- Screenshot audit rules:
  `references/screenshot-audit-rubric.md`
- Backend slices to frontend surfaces:
  `references/backend-slice-to-surface-map.md`
- Dialog/travel/combat closure checklist:
  `references/vertical-closure-checklist.md`

## Bundled scripts

- Sync the repo-local skill to the user's Codex home:
  `python .agents/skills/godot-crpg-shell-authority/scripts/sync_skill.py`

## Final review standard

Do not approve shell work unless a human can:

- start a new game
- read the screen
- understand the available actions
- move
- talk
- travel
- fight
- save
- load
- continue

without duplicate UI lies, unreadable labels, hidden prerequisites, or overlay collisions.
