"""Validation helpers for sidecar candidate batches created by content_orchestrator."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from tools.content_orchestrator import (
    DATA_DIR,
    DEFAULT_WORK_ROOT,
    EQUIPMENT_TYPES,
    FAMILY_SPECS,
    WORLDGEN_SECTION_KEYS,
    _item_bank,
    _load_json,
    _scalar_tag,
    _write_text,
    prepare_packets,
)


def _infer_signature(values: list[Any]) -> dict[str, Any]:
    if not values:
        return {"type": "any"}
    tags = {_scalar_tag(value) for value in values}
    if tags == {"dict"}:
        dicts = [value for value in values if isinstance(value, dict)]
        keys = sorted(set().union(*(value.keys() for value in dicts)))
        required = sorted(set.intersection(*(set(value) for value in dicts))) if dicts else []
        return {
            "type": "dict",
            "required": required,
            "allowed": keys,
            "fields": {key: _infer_signature([value[key] for value in dicts if key in value]) for key in keys},
        }
    if tags == {"list"}:
        items = [item for value in values for item in value]
        return {"type": "list", "item": _infer_signature(items)}
    return {"type": "scalar", "tags": sorted(tags)}


def _validate_signature(value: Any, signature: dict[str, Any], path: str, errors: list[str]) -> None:
    kind = signature["type"]
    if kind == "any":
        return
    if kind == "scalar":
        if _scalar_tag(value) not in set(signature["tags"]):
            errors.append(f"{path}: expected {signature['tags']}, got {_scalar_tag(value)}")
        return
    if kind == "list":
        if not isinstance(value, list):
            errors.append(f"{path}: expected list")
            return
        for index, item in enumerate(value):
            _validate_signature(item, signature["item"], f"{path}[{index}]", errors)
        return
    if not isinstance(value, dict):
        errors.append(f"{path}: expected dict")
        return
    missing = sorted(set(signature["required"]) - set(value))
    extras = sorted(set(value) - set(signature["allowed"]))
    if missing:
        errors.append(f"{path}: missing keys {', '.join(missing)}")
    if extras:
        errors.append(f"{path}: unexpected keys {', '.join(extras)}")
    for key, child_signature in signature["fields"].items():
        if key in value:
            _validate_signature(value[key], child_signature, f"{path}.{key}", errors)


def _validate_standard_list_family(name: str, payload: Any) -> list[str]:
    errors: list[str] = []
    spec = FAMILY_SPECS[name]
    source = _load_json(DATA_DIR / spec.source_files[0])[spec.collection_keys[0]]
    if name == "items_equipment":
        source = [entry for entry in source if entry.get("type") in EQUIPMENT_TYPES]
    if name == "items_supplies":
        source = [entry for entry in source if entry.get("type") not in EQUIPMENT_TYPES]
    key = spec.collection_keys[0]
    if not isinstance(payload, dict) or set(payload) != {key}:
        return [f"top-level keys must be exactly ['{key}']"]
    entries = payload[key]
    if not isinstance(entries, list):
        return [f"{key} must be a list"]
    signature = _infer_signature(source)
    identity = "id" if all("id" in entry for entry in source if isinstance(entry, dict)) else "name"
    existing = {entry.get(identity) for entry in source if isinstance(entry, dict)}
    seen: set[Any] = set()
    bank = _item_bank()
    for index, entry in enumerate(entries):
        _validate_signature(entry, signature, f"{key}[{index}]", errors)
        ident = entry.get(identity) if isinstance(entry, dict) else None
        if ident in seen:
            errors.append(f"{key}[{index}]: duplicate {identity} `{ident}` within candidate file")
        if ident in existing:
            errors.append(f"{key}[{index}]: {identity} `{ident}` already exists in source data")
        seen.add(ident)
        if name == "npc_templates" and isinstance(entry, dict):
            for item_id in entry.get("shop_inventory", []):
                if item_id not in bank["item_ids"]:
                    errors.append(f"{key}[{index}].shop_inventory references unknown item `{item_id}`")
            if entry.get("faction") not in bank["faction_ids"]:
                errors.append(f"{key}[{index}].faction references unknown faction `{entry.get('faction')}`")
        if name == "recipes" and isinstance(entry, dict):
            if entry.get("workstation") not in bank["workstation_ids"]:
                errors.append(f"{key}[{index}].workstation `{entry.get('workstation')}` is unsupported")
            if entry.get("skill") not in bank["recipe_skills"]:
                errors.append(f"{key}[{index}].skill `{entry.get('skill')}` is unsupported")
            for ingredient in entry.get("ingredients", []):
                if ingredient.get("item_id") not in bank["recipe_known_item_ids"]:
                    errors.append(f"{key}[{index}].ingredients references unknown item `{ingredient.get('item_id')}`")
            for product in entry.get("products", []):
                if product.get("item_id") not in bank["recipe_known_item_ids"]:
                    errors.append(f"{key}[{index}].products references unknown item `{product.get('item_id')}`")
            for tool in entry.get("tools", []):
                if tool not in bank["recipe_tools"] and tool not in bank["item_ids"]:
                    errors.append(f"{key}[{index}].tools references unknown tool `{tool}`")
        if name == "spells" and isinstance(entry, dict):
            if entry.get("school") not in bank["spell_schools"]:
                errors.append(f"{key}[{index}].school `{entry.get('school')}` is unsupported")
            if entry.get("target_type") not in bank["spell_target_types"]:
                errors.append(f"{key}[{index}].target_type `{entry.get('target_type')}` is unsupported")
        if name.startswith("items_") and isinstance(entry, dict):
            item_type = entry.get("type")
            if name == "items_equipment" and item_type not in EQUIPMENT_TYPES:
                errors.append(f"{key}[{index}].type `{item_type}` belongs in items_supplies")
            if name == "items_supplies" and item_type in EQUIPMENT_TYPES:
                errors.append(f"{key}[{index}].type `{item_type}` belongs in items_equipment")
    return errors


def _validate_campaigns(payload: Any) -> list[str]:
    errors: list[str] = []
    source = _load_json(DATA_DIR / "campaign_templates.json")["campaigns"]
    if not isinstance(payload, dict) or set(payload) != {"campaigns"}:
        return ["top-level keys must be exactly ['campaigns']"]
    entries = payload["campaigns"]
    if not isinstance(entries, list):
        return ["campaigns must be a list"]
    signature = _infer_signature(source)
    existing = {entry.get("id") for entry in source if isinstance(entry, dict)}
    seen: set[Any] = set()
    bank = _item_bank()
    for index, entry in enumerate(entries):
        _validate_signature(entry, signature, f"campaigns[{index}]", errors)
        ident = entry.get("id") if isinstance(entry, dict) else None
        if ident in seen:
            errors.append(f"campaigns[{index}]: duplicate id `{ident}` within candidate file")
        if ident in existing:
            errors.append(f"campaigns[{index}]: id `{ident}` already exists in source data")
        seen.add(ident)
        if not isinstance(entry, dict):
            continue
        if entry.get("difficulty") not in bank["campaign_difficulties"]:
            errors.append(f"campaigns[{index}].difficulty `{entry.get('difficulty')}` is unsupported")
        quest_ids = {quest.get("id") for quest in entry.get("quests", []) if isinstance(quest, dict)}
        for quest_index, quest in enumerate(entry.get("quests", [])):
            if not isinstance(quest, dict):
                continue
            for enemy_id in quest.get("enemy_ids", []):
                if enemy_id not in bank["monster_ids"]:
                    errors.append(f"campaigns[{index}].quests[{quest_index}] references unknown monster `{enemy_id}`")
            for item_id in (quest.get("rewards") or {}).get("items", []):
                if item_id not in bank["reward_item_ids"]:
                    errors.append(f"campaigns[{index}].quests[{quest_index}] rewards unknown item `{item_id}`")
            next_quest = quest.get("next_quest")
            if next_quest and next_quest not in quest_ids:
                errors.append(f"campaigns[{index}].quests[{quest_index}] next_quest `{next_quest}` is missing from the candidate campaign")
    return errors


def _validate_worldgen(payload: Any) -> list[str]:
    errors: list[str] = []
    source = _load_json(DATA_DIR / "worldgen.json")["worldgen"]
    if not isinstance(payload, dict) or set(payload) != {"worldgen"}:
        return ["top-level keys must be exactly ['worldgen']"]
    worldgen = payload["worldgen"]
    if not isinstance(worldgen, dict):
        return ["worldgen must be an object"]
    unknown = sorted(set(worldgen) - WORLDGEN_SECTION_KEYS)
    if unknown:
        errors.append(f"worldgen contains unsupported sections: {', '.join(unknown)}")
    for section, value in worldgen.items():
        if section not in source:
            errors.append(f"worldgen section `{section}` does not exist in source data")
            continue
        source_value = source[section]
        if section == "entity_templates_by_location":
            if not isinstance(value, dict):
                errors.append("worldgen.entity_templates_by_location must be an object")
                continue
            signatures = {name: _infer_signature([section_value]) for name, section_value in source_value.items()}
            for category, category_value in value.items():
                if category not in signatures:
                    errors.append(f"worldgen.entity_templates_by_location category `{category}` is unsupported")
                    continue
                _validate_signature(category_value, signatures[category], f"worldgen.entity_templates_by_location.{category}", errors)
            continue
        if isinstance(source_value, dict):
            if not isinstance(value, dict):
                errors.append(f"worldgen.{section} must be an object")
                continue
            signature = _infer_signature(list(source_value.values()))
            for candidate_key, candidate_value in value.items():
                _validate_signature(candidate_value, signature, f"worldgen.{section}.{candidate_key}", errors)
            continue
        _validate_signature(value, _infer_signature([source_value]), f"worldgen.{section}", errors)
    return errors


def _validate_bundle(payload: Any) -> list[str]:
    errors: list[str] = []
    allowed = {"campaigns", "history_tables", "social_rules"}
    if not isinstance(payload, dict) or not payload or not set(payload).issubset(allowed):
        return ["bundle candidate must contain one or more of: campaigns, history_tables, social_rules"]
    if "campaigns" in payload:
        errors.extend(_validate_campaigns({"campaigns": payload["campaigns"]}))
    history_source = _load_json(DATA_DIR / "history_tables.json")["history_tables"]
    if "history_tables" in payload:
        history = payload["history_tables"]
        if not isinstance(history, dict):
            errors.append("history_tables must be an object")
        else:
            for key, value in history.items():
                if key not in history_source:
                    errors.append(f"history_tables key `{key}` does not exist in source")
                    continue
                _validate_signature(value, _infer_signature([history_source[key]]), f"history_tables.{key}", errors)
    social_source = _load_json(DATA_DIR / "social_rules.json")["social_rules"]
    bank = _item_bank()
    if "social_rules" in payload:
        social = payload["social_rules"]
        if not isinstance(social, dict):
            errors.append("social_rules must be an object")
        else:
            for key, value in social.items():
                if key not in social_source:
                    errors.append(f"social_rules key `{key}` does not exist in source")
                    continue
                _validate_signature(value, _infer_signature([social_source[key]]), f"social_rules.{key}", errors)
            for role, attitude in social.get("default_npc_attitude", {}).items():
                if role not in bank["npc_roles"]:
                    errors.append(f"social_rules.default_npc_attitude role `{role}` is unknown")
                if attitude not in bank["default_npc_attitudes"]:
                    errors.append(f"social_rules.default_npc_attitude attitude `{attitude}` is unknown")
            for role, alignment in social.get("default_npc_alignment", {}).items():
                if role not in bank["npc_roles"]:
                    errors.append(f"social_rules.default_npc_alignment role `{role}` is unknown")
                if alignment not in bank["default_npc_alignments"]:
                    errors.append(f"social_rules.default_npc_alignment alignment `{alignment}` is unknown")
    return errors


def _near_duplicate_warnings(payload: Any) -> list[str]:
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return warnings
    for key, value in payload.items():
        if isinstance(value, list):
            labels = [
                str(entry.get("id") or entry.get("name") or entry)
                for entry in value
                if isinstance(entry, dict)
            ]
            for index, left in enumerate(labels):
                for right in labels[index + 1:]:
                    ratio = difflib.SequenceMatcher(a=left.lower(), b=right.lower()).ratio()
                    if ratio >= 0.88:
                        warnings.append(f"{key}: near-duplicate candidate labels `{left}` and `{right}`")
        if key == "worldgen" and isinstance(value, dict):
            for section, section_value in value.items():
                if not isinstance(section_value, dict):
                    continue
                names = list(section_value)
                for index, left in enumerate(names):
                    for right in names[index + 1:]:
                        ratio = difflib.SequenceMatcher(a=left.lower(), b=right.lower()).ratio()
                        if ratio >= 0.92:
                            warnings.append(f"worldgen.{section}: near-duplicate keys `{left}` and `{right}`")
    return warnings


def validate_batches(batch_id: str | None = None, work_root: Path | None = None, strict_missing: bool = True) -> dict[str, Any]:
    root = work_root or DEFAULT_WORK_ROOT
    manifest = _load_json(root / "tmp" / "content_packets" / "manifest.json")
    if batch_id and manifest["batch_id"] != batch_id:
        raise ValueError(f"manifest batch_id {manifest['batch_id']} does not match requested {batch_id}")
    results = {"batch_id": manifest["batch_id"], "families": [], "overall_status": "pass"}
    for family in manifest["families"]:
        name = family["name"]
        candidate_path = Path(family["candidate"])
        review_path = Path(family["review"])
        entry = {"name": name, "candidate": str(candidate_path), "review": str(review_path), "status": "pass", "errors": [], "warnings": []}
        if not candidate_path.exists():
            entry["status"] = "missing"
            message = f"candidate file missing: {candidate_path}"
            (entry["errors"] if strict_missing else entry["warnings"]).append(message)
        else:
            payload = _load_json(candidate_path)
            errors = _validate_worldgen(payload) if name == "worldgen" else _validate_bundle(payload) if name == "campaign_history_social" else _validate_standard_list_family(name, payload)
            entry["errors"].extend(errors)
            entry["warnings"].extend(_near_duplicate_warnings(payload))
            if errors:
                entry["status"] = "fail"
        if not review_path.exists():
            entry["warnings"].append(f"review report missing: {review_path}")
        if entry["errors"]:
            results["overall_status"] = "fail"
        elif entry["status"] == "missing" and strict_missing and results["overall_status"] != "fail":
            results["overall_status"] = "fail"
        elif entry["warnings"] and results["overall_status"] == "pass":
            results["overall_status"] = "pass_with_warnings"
        results["families"].append(entry)
    lines = [
        "# Content Validation Summary",
        "",
        f"- Batch ID: `{results['batch_id']}`",
        f"- Overall status: `{results['overall_status']}`",
        "",
        "| Family | Status | Candidate | Review |",
        "| --- | --- | --- | --- |",
    ]
    for entry in results["families"]:
        lines.append(f"| `{entry['name']}` | `{entry['status']}` | `{entry['candidate']}` | `{entry['review']}` |")
        for line in entry["errors"]:
            lines.append(f"- ERROR `{entry['name']}`: {line}")
        for line in entry["warnings"]:
            lines.append(f"- WARN `{entry['name']}`: {line}")
    _write_text(root / "reports" / "content_validation_summary.md", "\n".join(lines))
    return results


def run_dry_run(batch_id: str | None = None, work_root: Path | None = None) -> dict[str, Any]:
    manifest = prepare_packets(batch_id=batch_id, work_root=work_root)
    return validate_batches(batch_id=manifest["batch_id"], work_root=work_root, strict_missing=False)
