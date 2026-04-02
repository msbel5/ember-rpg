# PRD: Godot UX and Accessibility V1
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-04-02  
**Status:** In Progress  

---

## 1. Purpose
Define the measurable UX and accessibility bar for the shipped Godot client. This PRD converts general polish goals into auditable requirements using `WCAG 2.2 AA`, `Xbox Accessibility Guidelines`, and `Nielsen heuristics` as the evaluation basis for Ember's screen set.

## 2. Scope
- In scope: title, continue browser, creation phases, gameplay shell, character, settlement, inventory, quests, save/load, combat, minimap/world graph/travel, screenshot-proof artifacts, and per-screen UX scorecards.
- Out of scope: marketing site UX, launcher UX, deep controller remapping, and speculative redesign outside the current product contract.

## 3. Standards Baseline
- `WCAG 2.2 AA`: contrast, focus visibility, target size, keyboard completeness, state clarity.
- `Xbox Accessibility Guidelines`: legibility, redundant cues, readable interaction surfaces, clear input expectations.
- `Nielsen heuristics`: system status visibility, consistency, error prevention, recognition over recall.

## 4. Functional Requirements
FR-01: The primary layout baseline SHALL be `1600x900`; `1280x720` is fallback only.

FR-02: Every primary screen SHALL have a documented screenshot-proof pair:
- viewport proof
- desktop/window proof when applicable

FR-03: Every actionable control SHALL expose visible focus and keyboard access.

FR-04: Primary text and critical labels SHALL maintain readable contrast against their backgrounds.

FR-05: Interactive states SHALL be distinguishable through more than color alone where feasible.

FR-06: Each screen SHALL communicate current state, next action, and error conditions without requiring hidden knowledge.

FR-07: The UX audit SHALL produce a per-screen scorecard and a failed-criteria list before polish is considered complete.

## 5. Screen Inventory
- Title
- Continue browser
- Creation: Identity / Questionnaire / Roll / Build / Dossier
- Gameplay shell
- Character
- Settlement
- Inventory
- Quests
- Save/load
- Combat
- Minimap / world graph / travel

## 6. Acceptance Criteria
AC-01 [FR-01]: The active client layout and proof captures are produced at `1600x900` baseline.

AC-02 [FR-02]: Every screen in the inventory has a viewport proof artifact, and desktop/window proof where the executor supports it.

AC-03 [FR-03]: Keyboard traversal can reach all primary actions on every inventory screen.

AC-04 [FR-04]: Critical labels, buttons, and state text meet the chosen contrast bar in the audit.

AC-05 [FR-05]: Disabled, busy, selected, and error states are not communicated by color alone.

AC-06 [FR-06]: Each screen exposes system status and the next meaningful action clearly enough to pass the audit rubric.

AC-07 [FR-07]: The UX audit produces scorecards, failed-criteria lists, and post-fix proof artifacts.

## 7. Evidence Targets
- `docs/qa/demo_signoff_matrix.md`
- `docs/qa/final_polish_visual_log.md`
- `docs/qa/proof_reports/20260402/`
- `tmp/visual_automation/`
- `tmp/visual_probe/`

## 8. Current Cycle Note
- Current bounded proof coverage exists for title/creation, sidebar hydration, save/load, dialog, travel, and combat through semantic desktop reports in `docs/qa/proof_reports/20260402/`.
- The full per-screen UX scorecard set is still open work; this PRD remains active until contrast, focus, target-size, keyboard, and state-clarity audits are documented screen by screen.

## Changelog
- 2026-04-01: Added as the formal UX/accessibility audit contract for the Godot-first release surface.
- 2026-04-02: Added the current bounded proof evidence root and marked the audit as in progress rather than complete.
