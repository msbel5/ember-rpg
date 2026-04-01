# PRD: Colony Simulation Kernel V1
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Colony Simulation Kernel V1 defines the typed runtime state that turns a static settlement into a living colony. The goal is to unify needs, schedules, production, shortages, morale, safety, and event pressure into explicit records rather than unrelated helper modules.

## 2. Scope
- In scope: `NeedState`, `ScheduleState`, `ProductionLedger`, `ColonyPressureState`, deterministic pressure updates, quest hook outputs.
- Out of scope: final UI dashboards, AI narration, diplomacy resolution.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M03 Need / Happiness / Stress, M11 Trade, M12 Migration / Population, M13 Strange Mood, M16 Building / Room Assignment, M19 Farming.
- Dependency guardrail: needs, pressure, supply, room quality, and shortage signals must continue to feed quest hooks and behavior changes without any LLM dependency.

## 4. Functional Requirements (FR)
FR-01: The backend must define a typed `NeedState` suitable for actor-level storage.

FR-02: The backend must define a typed `ScheduleState` suitable for actor-level storage.

FR-03: The backend must define a typed `ProductionLedger` for stock, input, output, and shortage accounting.

FR-04: The backend must define a typed `ColonyPressureState` for food, safety, morale, supply, and unrest.

FR-05: Colony pressure must be derivable from deterministic runtime state with no LLM dependency.

FR-06: Quest seeds must be derivable from typed colony pressure and shortage state.

## 5. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given an actor with needs and a schedule, when the colony state is serialized, then both are present as typed snapshots.

AC-02 [FR-03]: Given production inputs and outputs, when the colony ledger updates, then shortages and stock changes are explicit.

AC-03 [FR-04]: Given supply and safety degradation, when colony pressure is recalculated, then pressure fields change deterministically.

AC-04 [FR-05, FR-06]: Given a severe shortage or safety collapse, when quest hooks are generated, then they derive from deterministic colony pressure rather than authored text tables alone.

## 6. Integration Points
- actor kernel
- job/reaction kernel
- world tick
- quest generation

## 7. Test Coverage Target
- need decay and schedule state adaptation
- shortage propagation
- pressure-to-quest hook generation
