# Shell Layout Rubric

## Purpose

This rubric defines the intended Ember gameplay shell.

## Canonical shell

- Top strip: compact global state only
- Center: world viewport
- Right panel: contextual information surface
- Bottom bar: actionable verbs and text input

## Top strip

Allowed:

- location
- time or day/hour
- gold
- HP and one compact health bar

Forbidden:

- duplicate class sheet
- duplicate AP or combatant roster if already shown elsewhere
- repeated location or scene summaries

## World viewport

Allowed:

- actor labels
- temporary hover/focus hints
- one active combat overlay
- one active dialog overlay

Forbidden:

- permanent duplicate headers
- simultaneous combat and non-combat overlays covering the same region
- unexplained debug banners in the player path

## Right contextual panel

Owns:

- narrative
- hero
- town
- quests
- items
- map

Must not repeat the top strip.

## Bottom action bar

Must contain only real verbs:

- Talk
- Attack
- Examine
- Use
- Rest

Text input remains allowed for freeform commands, but the button layer must match actual gameplay verbs.
