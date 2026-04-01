# PRD: Godot Client Sprint 5

## Objective

Integrate the asset pipeline so the client can consume generated 16x16 art with deterministic fallback behavior.

## Scope

- Extend the Python asset pipeline for 16x16 output and manifest metadata.
- Add Godot-side asset bootstrap and lookup order.
- Allow optional async desktop runtime generation.

## Files

- `tools/asset_pipeline.py`
- `godot-client/scripts/asset/asset_bootstrap.gd`
- `godot-client/scripts/asset/asset_manifest.gd`
- `godot-client/scripts/world/tile_catalog.gd`
- `godot-client/scripts/world/entity_sprite_catalog.gd`

## Data Contract

- `user://assets/generated/...`
- `res://assets/generated/...`
- placeholders as final fallback

## GDScript Structure

- `asset_manifest.gd` reads manifest metadata and exposes lookup helpers.
- `tile_catalog.gd` and `entity_sprite_catalog.gd` resolve generated assets before placeholders.
- Runtime generation runs asynchronously and never blocks scene boot.

## Acceptance Criteria

- Missing generated assets do not break play.
- Token lookup works with `HF_TOKEN` or `HUGGINGFACE_API_KEY`.
- Cached generated assets load on the next run without regeneration.
