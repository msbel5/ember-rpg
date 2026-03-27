# PRD: RimWorld Benchmark v1
**Project:** Ember RPG  
**Phase:** 5  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Approved  

---

## 1. Purpose
Define the benchmark rubric used to compare Ember RPG’s avatar-commander experience against RimWorld. The benchmark exists to turn “AAA quality” into measurable systems, visual, and UX targets without cloning RimWorld’s exact design.

## 2. Scope
- In scope: comparison rubric, scoring scale, evidence requirements, and sign-off thresholds for systems, visuals, and user experience.
- Out of scope: copying RimWorld’s art direction, exact UI layout, or colony-management focus.

## 3. Functional Requirements (FR)
FR-01: The benchmark must score Ember on three axes: systems clarity, visual readability, and UX loop quality.
FR-02: Each axis must contain concrete rubric categories with a 1-5 score scale.
FR-03: Every category must require evidence: targeted tests, screenshots, or playtest notes.
FR-04: The benchmark must be applicable to both `fantasy_ember` and `scifi_frontier`.
FR-05: The benchmark must define minimum release gates for a playable milestone.
FR-06: The benchmark document must list explicit non-goals so Ember remains an avatar-commander hybrid rather than a colony-sim clone.

## 4. Data Structures
```python
class BenchmarkScore(TypedDict):
    category: str
    score: int
    evidence: list[str]

class BenchmarkReport(TypedDict):
    adapter_id: str
    systems: list[BenchmarkScore]
    visuals: list[BenchmarkScore]
    ux: list[BenchmarkScore]
    open_gaps: list[str]
```

## 5. Public API
There is no runtime code API for this PRD. The public process interface is:
```text
1. Run targeted tests.
2. Capture OS + viewport screenshots.
3. Perform timed playtests.
4. Score each rubric category.
5. Record open gaps and release decision.
```

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The benchmark defines the three major axes: systems, visuals, and UX.
AC-02 [FR-02]: Each axis includes category-level scores on a 1-5 scale.
AC-03 [FR-03]: The document requires evidence for every score.
AC-04 [FR-04]: The scoring process applies to both live adapters.
AC-05 [FR-05]: A release gate is defined: no axis average below 3, no critical open bug, and no failed save/load or visual readability blocker.
AC-06 [FR-06]: The document explicitly states that Ember is not pivoting into a pure colony-management clone.

## 7. Performance Requirements
- Normal player commands should produce visible feedback in under 1 second during benchmark playtests.
- Region loads should complete in under 2 seconds on developer hardware.
- Benchmark documentation updates should be lightweight enough to complete inside a single sprint closeout.

## 8. Error Handling
- If evidence is missing for a score, that category is automatically marked “unverified”.
- If one adapter fails the benchmark while the other passes, the rollout remains blocked for both unless the milestone is explicitly adapter-scoped.
- Subjective “feels good” claims without rubric evidence are not accepted as closure.

## 9. Integration Points
- Feeds release sign-off for campaign runtime, terminal client, and Godot client.
- Consumes artifacts from backend chaos runs, Godot viewport captures, and manual playtest logs.
- Produces the gap-analysis document referenced by QA and polish work.

## 10. Test Coverage Target
- Every rubric category must map to at least one automated test or one explicit manual visual acceptance entry.
- Required evidence sources: backend targeted tests, Godot visual proofs, and campaign playtest notes.

## Changelog
- 2026-03-27: Initial approved benchmark PRD for RimWorld-style quality comparison.
