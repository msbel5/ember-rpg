# PRD: Job and Reaction Kernel V1
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Codex  
**Date:** 2026-03-31  
**Status:** Draft  

---

## 1. Purpose
Job and Reaction Kernel V1 defines the typed work system that connects actors, worksites, recipes, and deterministic outputs. The goal is to replace scattered crafting and workstation assumptions with explicit job records and reaction definitions that later support colony production chains.

## 2. Scope
- In scope: `JobRecord`, `ReactionDef`, `WorksiteRecord`, typed inputs/outputs, actor assignment, completion tracking.
- Out of scope: full UI job queue tooling, late-game industry balancing, trade-caravan behavior.

## 3. Reference Mechanism Coverage
- Primary DF-inspired coverage: M02 Skill / Learning, M04 Job / Task Assignment, M16 Building / Room Assignment, M19 Farming.
- Dependency guardrail: job completion must still feed skill growth, item creation, building progression, and colony supply without bypassing typed work records.

## 4. Functional Requirements (FR)
FR-01: The backend must define a typed `JobRecord`.

FR-02: `JobRecord` must store:
- job id
- job type
- worker actor id
- worksite id
- required skill
- required inputs
- expected outputs
- completion state

FR-03: The backend must define a typed `ReactionDef`.

FR-04: `ReactionDef` must describe deterministic input/output transformations, not free-form handler code only.

FR-05: The backend must define a typed `WorksiteRecord`.

FR-06: Current workstation and recipe logic must be promotable into this typed surface incrementally.

## 5. Acceptance Criteria (AC)
AC-01 [FR-01, FR-02]: Given a queued job, when it is serialized, then worker, worksite, skill, and completion metadata round-trip.

AC-02 [FR-03, FR-04]: Given a reaction definition, when the kernel inspects it, then deterministic inputs and outputs are explicit.

AC-03 [FR-05]: Given a worksite, when jobs are attached, then the relation is represented through typed ids rather than ad hoc handler locals.

AC-04 [FR-06]: Given an existing crafting payload, when it is promoted, then typed job/reaction records can represent it without breaking current command routes.

## 6. Integration Points
- inventory/crafting handlers
- colony simulation kernel
- future economy and quest hooks

## 7. Test Coverage Target
- job serialization
- reaction input/output validation
- worksite attachment
