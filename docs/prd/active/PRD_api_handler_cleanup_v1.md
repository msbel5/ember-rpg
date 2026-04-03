# PRD: API Handler Cleanup v1

**Status:** In Progress
**Phase:** 5
**Date:** 2026-04-03

## Summary

Create a kernel adapter module that API handlers can import instead of
legacy core modules. This provides a clean import boundary -- handlers
import from `engine.kernel` only, not `engine.core`.

## Key Deliverable

`engine/api/kernel_adapter.py` -- a facade that exposes kernel combat,
actor creation, and effect operations to API handlers, replacing direct
imports from engine.core.combat, engine.core.character, etc.

## Acceptance Criteria

- **AC-01:** kernel_adapter exposes create_player, create_monster, combat ops.
- **AC-02:** kernel_adapter has zero imports from engine.core.
- **AC-03:** Tests verify the adapter's public API works end-to-end.

## Files

- NEW: `engine/api/kernel_adapter.py`
- NEW: `tests/test_kernel_adapter.py`
