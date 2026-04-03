# PRD: Data Externalization v1

**Status:** Implemented
**Phase:** 6
**Date:** 2026-04-03

## Summary

Externalize hardcoded game constants from Python code into JSON data files.
Add a data_loader module that reads from data/*.json with caching.

## Externalized Data

- `data/materials.json` -- 10 material definitions with physical properties
- `data/quality_tiers.json` -- 7 quality tier multipliers (Poor to Legendary)

## Acceptance Criteria

- **AC-01:** Materials load from JSON with all required fields.
- **AC-02:** Quality tiers load from JSON in monotonic order.
- **AC-03:** Missing data file raises clear FileNotFoundError.
- **AC-04:** Data loader caches results per-process.
