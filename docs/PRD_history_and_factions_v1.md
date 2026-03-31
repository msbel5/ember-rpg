# PRD: History and Factions Kernel V1
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
History and Factions Kernel V1 defines the typed social-political layer that macro world state depends on. The goal is to promote faction seeds and historical events into stable records that can later drive diplomacy, ownership, legends, migration pressure, and long-form quest context.

## 2. Scope
- In scope: typed faction records, typed history figures, typed history events, ownership and presence links, serialization.
- Out of scope: full legend browser, procedural prose, diplomacy UI, religion systems.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M12 Migration / Population, M14 World Generation, M20 Diplomacy.
- Dependency guardrail: faction presence, ownership, history events, and diplomacy triggers must remain typed links rather than narrative-only metadata.

## 4. Functional Requirements (FR)
FR-01: The backend must define a typed `FactionRecord`.

FR-02: `FactionRecord` must store at minimum:
- faction id
- culture id
- species id
- origin region id
- traits
- region presence

FR-03: The backend must define a typed `HistoryFigure`.

FR-04: The backend must define a typed `HistoryEvent`.

FR-05: Site ownership and faction presence must become typed links instead of incidental dict payloads.

FR-06: Existing worldgen historical events must be promotable into typed history records.

## 5. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given seeded factions, when they are adapted, then origin and presence data are stored in typed fields.

AC-02 [FR-03, FR-04]: Given generated historical data, when it is adapted, then figures and events are separately typed and serializable.

AC-03 [FR-05]: Given a site and an owning faction, when world state is serialized, then the ownership link round-trips without depending on UI payload assembly.

AC-04 [FR-06]: Given two identical world seeds, when history is adapted twice, then event ordering and identifiers remain deterministic.

## 6. Integration Points
- world-state kernel
- worldgen history simulation
- future diplomacy and quest systems

## 7. Test Coverage Target
- faction origin/presence adaptation
- history event serialization
- ownership link round-trip
