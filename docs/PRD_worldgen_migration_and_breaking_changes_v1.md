# PRD: Worldgen Migration and Breaking Changes v1
**Project:** Ember RPG  
**Phase:** Migration  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Define how Ember RPG migrates from the legacy town/history/world-state slice to the new world simulation kernel, including deliberate breaking changes, test rewrite sequencing, and replacement of old assumptions.

## 2. Scope
- In scope: breaking changes, deprecated modules and data, test migration sequence, and runtime ownership changes.
- Out of scope: preserving old save compatibility or maintaining legacy faction IDs as permanent contracts.

## 3. Functional Requirements (FR)
FR-01: The migration must replace legacy fixed-faction and shallow-history assumptions with simulation-derived factions and event ledgers.
FR-02: Old save compatibility is not required and may be removed.
FR-03: Legacy `engine.map` and `engine.world.history` tests may remain only as temporary anchors until the new kernel reaches their functional domain.
FR-04: The migration must introduce targeted new tests before replacing legacy tests.
FR-05: The migration must redirect runtime/session APIs from legacy world state to the new kernel snapshots once the corresponding new tests pass.
FR-06: Breaking changes must be documented in one place so downstream client and API work knows which contracts changed.

## 4. Data Structures
```python
@dataclass
class BreakingChange:
    area: str
    old_contract: str
    new_contract: str
    test_gate: str
```

## 5. Public API
```python
def list_breaking_changes() -> list[BreakingChange]
def migration_ready(checkpoint: str) -> bool
```
- Preconditions: migration checkpoints must be named in code or documentation.
- Postconditions: each checkpoint maps to test gates and runtime ownership changes.
- Exceptions: unknown checkpoints raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The migration document explicitly states that fixed legacy faction IDs are no longer engine-level contracts.
AC-02 [FR-02]: The migration document explicitly states that old saves are unsupported after the kernel cutover.
AC-03 [FR-03]: Legacy test files are identified as temporary anchors and not permanent canonical contracts.
AC-04 [FR-04]: Each replacement module has at least one targeted new test file listed before code cutover.
AC-05 [FR-05]: Runtime API ownership changes are mapped to milestone gates.
AC-06 [FR-06]: A downstream engineer can identify which routes, maps, and state snapshots change during the migration.

## 7. Performance Requirements
- Not a runtime module. No direct runtime budget.

## 8. Error Handling
- If migration checkpoints are incomplete, runtime ownership must not flip to the new kernel.
- If a new targeted suite fails, legacy runtime ownership must remain in place until the gate is green.

## 9. Integration Points
- Guides backend route migration, save/load ownership, terminal client updates, and future Godot consumption.
- Works with the master architecture PRD and runtime PRD as the operational cutover guide.

## 10. Test Coverage Target
- Documentation review plus targeted migration helper tests if code is added.

## Changelog
- 2026-03-27: Initial migration PRD for the world simulation rewrite.
