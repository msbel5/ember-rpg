# PRD: Documentation Inventory Matrix
**Project:** Ember RPG
**Phase:** 0
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-02
**Status:** Approved

---

## 1. Purpose

Define the governance contract for Ember RPG documentation inventory. This PRD does not duplicate the rendered matrix; it points to the canonical generated artifact and defines where active PRDs, deprecated PRDs, and registry metadata must live.

## 2. Canonical Artifact

- The generated implementation matrix lives at `docs/PRD_IMPLEMENTATION_MATRIX.md`.
- It is rendered from `docs/doc_registry.json` by `python -m tools.doc_inventory`.
- Tests validate the root artifact directly. `docs/prd/active/PRD_IMPLEMENTATION_MATRIX.md` is a governance pointer only.

## 3. Rules

- Active PRDs live only under `docs/prd/active/`.
- Deprecated PRDs live only under `docs/deprecated/prd/`.
- Deprecated planning notes live only under `docs/deprecated/notes/`.
- Every active PRD must have registry metadata in `docs/doc_registry.json`.
- The root generated matrix is the only rendered inventory source that may be referenced as authoritative.

## 4. Acceptance Criteria

- `frp-backend/tests/test_doc_inventory.py` passes.
- `docs/PRD_IMPLEMENTATION_MATRIX.md` matches the exact renderer output.
- No active PRD exists without registry metadata.
- No duplicate generated matrix is treated as authoritative.
