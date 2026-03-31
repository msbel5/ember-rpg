# PRD: Hybrid Commander Loop V1
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Hybrid Commander Loop V1 defines how macro colony/world play and local commander-avatar play coexist under a single deterministic runtime. The goal is to let the player manage pressure at the node/site level while still walking, talking, fighting, and inspecting the active site in person.

## 2. Scope
- In scope: macro vs local loop boundaries, travel transitions, active-site hydration, commander-avatar continuity, deterministic tick ownership.
- Out of scope: LLM narration, final map polish, final tutorial onboarding.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M15 Pathfinding, M18 Military, plus the commander-facing consequences of M01 Combat and M20 Diplomacy.
- Dependency guardrail: macro travel, local action resolution, and future squad orders must all advance the same world tick and read the same world-state authority.

## 4. Functional Requirements (FR)
FR-01: The game must expose a macro loop where the player inspects world graph pressure, factions, sites, and travel routes.

FR-02: The game must expose a local loop where the commander-avatar operates inside the currently active site or region.

FR-03: Travel must be an explicit state transition between macro nodes, not a string-matched shortcut.

FR-04: The local map must be hydrated only for the active node or site.

FR-05: Macro pressure and local avatar actions must advance the same deterministic world tick.

FR-06: AI narration and NPC conversation must remain optional adapters, not authorities.

## 5. Acceptance Criteria (AC)
AC-01 [FR-01]: Given a campaign snapshot, when the player opens macro state, then world graph, faction pressure, and travel options are explicit.

AC-02 [FR-02]: Given an active site, when the player enters local play, then the commander-avatar can act without leaving deterministic world ownership.

AC-03 [FR-03, FR-04]: Given a destination node, when travel completes, then the active site changes and the local map rehydrates for the new destination only.

AC-04 [FR-05]: Given local actions consume turns, when time advances, then colony/world pressure also updates on the same timeline.

AC-05 [FR-06]: Given narrator or NPC response adapters are absent, when the loop runs, then core gameplay remains fully playable.

## 6. Integration Points
- world-state kernel
- actor kernel
- colony simulation kernel
- campaign runtime and Godot map/session surfaces

## 7. Test Coverage Target
- active-node travel integration
- shared tick progression
- local rehydrate correctness
