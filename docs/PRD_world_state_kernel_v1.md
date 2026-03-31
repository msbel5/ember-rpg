# PRD: World State Kernel V1
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
World State Kernel V1 defines the typed macro-world authority that sits above active local maps. The goal is to replace loosely-shaped world graph payloads with a canonical `WorldState` surface that owns regions, sites, settlements, factions, travel edges, and macro runtime metadata.

## 2. Scope
- In scope: typed world-state records, region/site/settlement/faction/travel structures, adapter from `WorldBlueprint`, serialization, save/load round-trip.
- Out of scope: local tile realization internals, detailed history simulation rules, final economy model, UI rendering.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M11 Trade, M12 Migration / Population, M14 World Generation, M20 Diplomacy.
- Dependency guardrail: world generation, settlement ownership, travel topology, faction presence, and macro economy hooks must land in the same canonical world record.

## 4. Functional Requirements (FR)
FR-01: The backend must define a typed `WorldState` root record.

FR-02: `WorldState` must explicitly contain typed `RegionRecord`, `SiteRecord`, `SettlementRecord`, `FactionRecord`, and `TravelEdge` entries.

FR-03: The active macro region must be stored as canonical state rather than only inferred from campaign payload assembly.

FR-04: The kernel must expose an adapter from `engine.worldgen.models.WorldBlueprint`.

FR-05: Typed world-state records must preserve the current world graph:
- regions
- settlement nodes
- travel edges
- faction presence
- region economy
- region alerts

FR-06: `WorldState` must round-trip through dict serialization with no loss of graph topology.

## 5. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given a generated world blueprint, when it is adapted, then a typed `WorldState` exists with explicit region, settlement, site, faction, and edge collections.

AC-02 [FR-03]: Given an active region id is present in the simulation snapshot, when the world is adapted, then `WorldState.active_region_id` preserves it.

AC-03 [FR-04, FR-05]: Given a deterministic world seed, when two world blueprints are adapted separately, then the resulting typed graph topology matches.

AC-04 [FR-06]: Given a typed world state, when it is serialized and restored, then region ids, edge endpoints, and settlement placements round-trip exactly.

## 6. Integration Points
- `frp-backend/engine/worldgen/models.py`
- `frp-backend/engine/worldgen/pipeline.py`
- `frp-backend/engine/api/campaign_state.py`
- save/load surfaces

## 7. Test Coverage Target
- deterministic world-state adaptation
- save/load round-trip
- graph connectivity preservation
