# PRD Standard — Ember RPG

All Product Requirement Documents in this project follow this template.
Lower-level models (Sonnet, Haiku) use PRDs as the **single source of truth** for TDD implementation.
A PRD must be complete enough that a developer who has never seen the codebase can implement it correctly.

---

## Template

```markdown
# PRD: [Module Name]
**Project:** Ember RPG  
**Phase:** [N]  
**Author:** Alcyone (CAPTAIN)  
**Date:** YYYY-MM-DD  
**Status:** Draft | Approved | Implemented  

---

## 1. Purpose
One paragraph. What does this module do and why does it exist?

## 2. Scope
- In scope: what this module handles
- Out of scope: what it deliberately does NOT handle

## 3. Functional Requirements (FR)
Numbered list. Each FR is a concrete, testable behavior.
FR-01: ...
FR-02: ...

## 4. Data Structures
Pseudocode or Python dataclass definitions for all public types.

## 5. Public API
Method signatures with parameter types, return types, and behavior description.
Include: preconditions, postconditions, exceptions raised.

## 6. Acceptance Criteria (AC)
Each AC is a named, independently verifiable condition.
Maps 1-to-1 with test cases. Written before implementation.

AC-01 [FR-01]: Given X, when Y, then Z.
AC-02 [FR-02]: ...

## 7. Performance Requirements
Latency / throughput constraints (if applicable).

## 8. Error Handling
What happens on invalid input, missing data, boundary conditions.

## 9. Integration Points
Which other modules this module calls / depends on.

## 10. Test Coverage Target
Minimum coverage %, specific branches that must be tested.
```

---

## Rules

1. **Language:** All PRDs are written in English. No exceptions.
2. **AC before implementation:** Acceptance Criteria are written BEFORE any code is written.
3. **One AC = one test:** Each AC should map directly to at least one pytest test case.
4. **No ambiguity:** Each requirement must be testable. "Should be fast" is not acceptable. "Must complete in < 50ms" is.
5. **Versioning:** When a PRD is updated post-implementation, add a `## Changelog` section at the bottom.
