"""Merge validated candidate content into primary data files.

Handles all JSON structure patterns:
  - List with wrapper key (items, monsters, npc_templates, spells, ...)
  - Bare list (interaction_rules)
  - Dict keyed by ID (materials, caravans, classes)
  - Nested sections (worldgen, factions, colony_config, ...)
  - Deep nested (name_banks 3-level, institutions town→role)

Usage:
    python -m tools.content_orchestrator merge --batch-id full_gen
    python -m tools.content_orchestrator merge --batch-id full_gen --dry-run
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "frp-backend" / "data"

# Identity field overrides per family (default: "id").
IDENTITY_FIELDS: dict[str, str] = {
    "spells": "name",
    "dialog_defs": "dialog_id",
    "consequence_rules": "rule_id",
}

# Families where the source file is a bare list (no wrapper key).
BARE_LIST_FAMILIES = {"interaction_rules"}

# Families with dict-keyed entries (not lists).
DICT_KEYED_FAMILIES = {"materials", "caravans", "classes"}

# Families requiring deep section merge (nested dicts, not append).
DEEP_MERGE_FAMILIES = {
    "worldgen", "factions", "colony_config", "economy_config", "quest_config",
    "campaign_history_social", "progression", "name_banks", "schedules",
    "institutions", "locations", "character_creation", "campaign_runtime",
    "loot_tables", "interaction_rules",
    "world_biomes", "world_species", "world_cultures", "world_buildings",
    "world_furniture", "world_quests",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _deep_merge(base: Any, new: Any) -> Any:
    """Recursively merge new into base. Lists are appended, dicts are merged."""
    if isinstance(base, dict) and isinstance(new, dict):
        result = dict(base)
        for key, value in new.items():
            if key in result:
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    if isinstance(base, list) and isinstance(new, list):
        # Deduplicate: skip entries already in base (by JSON equality).
        existing_strs = {json.dumps(e, sort_keys=True) for e in base}
        merged = list(base)
        for entry in new:
            if json.dumps(entry, sort_keys=True) not in existing_strs:
                merged.append(entry)
        return merged
    # Scalar: new value wins.
    return new


def merge_family(
    family_name: str,
    source_file: str,
    collection_key: str,
    candidate_path: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge a single family's candidate into the source data file.

    Returns: {"added": int, "skipped": int, "errors": list[str]}
    """
    source_path = DATA_DIR / source_file
    if not source_path.exists():
        return {"added": 0, "skipped": 0, "errors": [f"Source file not found: {source_file}"]}
    if not candidate_path.exists():
        return {"added": 0, "skipped": 0, "errors": [f"Candidate not found: {candidate_path}"]}

    source_data = _load_json(source_path)
    candidate_data = _load_json(candidate_path)
    added = 0
    skipped = 0
    errors: list[str] = []

    # --- Bare list (no wrapper key) ---
    if family_name in BARE_LIST_FAMILIES:
        if not isinstance(source_data, list):
            errors.append(f"Expected bare list in {source_file}, got {type(source_data).__name__}")
            return {"added": 0, "skipped": 0, "errors": errors}
        new_entries = candidate_data if isinstance(candidate_data, list) else []
        existing_strs = {json.dumps(e, sort_keys=True) for e in source_data}
        for entry in new_entries:
            if json.dumps(entry, sort_keys=True) in existing_strs:
                skipped += 1
            else:
                source_data.append(entry)
                added += 1
        if not dry_run and added > 0:
            _write_json(source_path, source_data)
        return {"added": added, "skipped": skipped, "errors": errors}

    # --- Deep merge families (nested sections) ---
    if family_name in DEEP_MERGE_FAMILIES:
        if collection_key and collection_key in source_data:
            original = source_data[collection_key]
            new_section = candidate_data.get(collection_key, candidate_data) if isinstance(candidate_data, dict) else candidate_data
            merged = _deep_merge(original, new_section)
            # Count changes.
            added = _count_new_keys(original, merged)
            source_data[collection_key] = merged
        else:
            merged = _deep_merge(source_data, candidate_data)
            added = _count_new_keys(source_data, merged)
            source_data = merged
        if not dry_run and added > 0:
            _write_json(source_path, source_data)
        return {"added": added, "skipped": 0, "errors": errors}

    # --- Dict-keyed families ---
    if family_name in DICT_KEYED_FAMILIES:
        target = source_data.get(collection_key, source_data) if collection_key else source_data
        raw_new = candidate_data.get(collection_key, candidate_data) if isinstance(candidate_data, dict) else candidate_data
        # Convert list candidates to dict if source is dict-keyed.
        new_dict = raw_new
        if isinstance(raw_new, list) and isinstance(target, dict):
            id_field = IDENTITY_FIELDS.get(family_name, "id")
            new_dict = {str(e.get(id_field, e.get("name", f"entry_{i}"))): e for i, e in enumerate(raw_new) if isinstance(e, dict)}
        if not isinstance(target, dict) or not isinstance(new_dict, dict):
            errors.append(f"Expected dict structure for {family_name}")
            return {"added": 0, "skipped": 0, "errors": errors}
        for key, value in new_dict.items():
            if key in target:
                skipped += 1
            else:
                target[key] = value
                added += 1
        if not dry_run and added > 0:
            _write_json(source_path, source_data)
        return {"added": added, "skipped": skipped, "errors": errors}

    # --- List with wrapper key (default pattern) ---
    if not collection_key:
        errors.append(f"No collection key for {family_name}")
        return {"added": 0, "skipped": 0, "errors": errors}
    source_list = source_data.get(collection_key, [])
    if not isinstance(source_list, list):
        errors.append(f"Expected list under '{collection_key}' in {source_file}")
        return {"added": 0, "skipped": 0, "errors": errors}
    new_list = candidate_data.get(collection_key, candidate_data if isinstance(candidate_data, list) else [])
    if isinstance(new_list, dict):
        new_list = list(new_list.values())
    id_field = IDENTITY_FIELDS.get(family_name, "id")
    existing_ids = {str(e.get(id_field, "")) for e in source_list if isinstance(e, dict)}
    for entry in new_list:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get(id_field, ""))
        if entry_id in existing_ids:
            skipped += 1
            logger.debug("Skip duplicate %s in %s", entry_id, family_name)
        else:
            source_list.append(entry)
            existing_ids.add(entry_id)
            added += 1
    source_data[collection_key] = source_list
    if not dry_run and added > 0:
        _write_json(source_path, source_data)
    return {"added": added, "skipped": skipped, "errors": errors}


def _count_new_keys(original: Any, merged: Any) -> int:
    """Count how many new keys/entries were added in a deep merge."""
    if isinstance(original, dict) and isinstance(merged, dict):
        new_keys = set(merged.keys()) - set(original.keys())
        count = len(new_keys)
        for key in original:
            if key in merged:
                count += _count_new_keys(original[key], merged[key])
        return count
    if isinstance(original, list) and isinstance(merged, list):
        return max(0, len(merged) - len(original))
    return 0


def merge_all(
    manifest_path: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge all candidate families from a manifest into primary data files."""
    from tools.content_orchestrator import FAMILY_SPECS

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    results: dict[str, Any] = {}

    for family in manifest.get("families", []):
        name = family["name"]
        spec = FAMILY_SPECS.get(name)
        if spec is None:
            results[name] = {"added": 0, "skipped": 0, "errors": [f"Unknown family: {name}"]}
            continue
        candidate_path = Path(family["candidate"])

        # Handle multi-file families (campaign_history_social).
        if len(spec.source_files) > 1:
            total_added = 0
            total_skipped = 0
            all_errors: list[str] = []
            for source_file, coll_key in zip(spec.source_files, spec.collection_keys):
                result = merge_family(name, source_file, coll_key, candidate_path, dry_run=dry_run)
                total_added += result["added"]
                total_skipped += result["skipped"]
                all_errors.extend(result["errors"])
            results[name] = {"added": total_added, "skipped": total_skipped, "errors": all_errors}
        else:
            source_file = spec.source_files[0]
            coll_key = spec.collection_keys[0] if spec.collection_keys else ""
            result = merge_family(name, source_file, coll_key, candidate_path, dry_run=dry_run)
            results[name] = result

        r = results[name]
        status = "OK" if not r["errors"] else "WARN"
        mode = "DRY-RUN" if dry_run else "MERGED"
        logger.info("[%s] %s: +%d added, %d skipped %s", mode, name, r["added"], r["skipped"],
                    f"({'; '.join(r['errors'])})" if r["errors"] else "")

    return results
