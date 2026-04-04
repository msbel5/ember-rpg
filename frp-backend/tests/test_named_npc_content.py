"""Named NPC authored-content validation tests."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SLUG_RE = re.compile(r"^[a-z0-9_]+$")
REQUIRED_TEMPLATE_ROLES = {
    "mayor",
    "priest",
    "bard",
    "scribe",
    "sage",
    "witch",
    "scout",
    "ranger",
    "magistrate",
    "ferryman",
    "miner",
    "quartermaster",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_templates() -> list[dict]:
    return _load_json(DATA_DIR / "npc_templates.json")["npc_templates"]


def _load_npcs() -> list[dict]:
    return _load_json(DATA_DIR / "npcs" / "npcs.json")["npcs"]


def _location_ids() -> set[str]:
    locations = _load_json(DATA_DIR / "locations.json")["locations"]["location_list"]
    return {entry["location_id"] for entry in locations}


def test_npc_templates_count_at_least_100():
    assert len(_load_templates()) >= 100


def test_named_npcs_count_at_least_100():
    assert len(_load_npcs()) >= 100


def test_template_roles_cover_required_families():
    roles = {entry["role"] for entry in _load_templates()}
    missing = REQUIRED_TEMPLATE_ROLES - roles
    assert not missing, f"Missing template role families: {sorted(missing)}"


def test_template_ids_unique_and_slugged():
    ids = [entry["id"] for entry in _load_templates()]
    duplicates = [entry_id for entry_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate template ids: {duplicates}"
    bad = [entry_id for entry_id in ids if not (entry_id.isascii() and entry_id == entry_id.lower() and SLUG_RE.match(entry_id))]
    assert not bad, f"Bad template ids: {bad}"


def test_named_npc_ids_unique_and_slugged():
    ids = [entry["id"] for entry in _load_npcs()]
    duplicates = [entry_id for entry_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate NPC ids: {duplicates}"
    bad = [entry_id for entry_id in ids if not (entry_id.isascii() and entry_id == entry_id.lower() and SLUG_RE.match(entry_id))]
    assert not bad, f"Bad NPC ids: {bad}"


def test_every_named_npc_role_maps_to_template_role():
    template_roles = {entry["role"] for entry in _load_templates()}
    missing = sorted({entry["role"] for entry in _load_npcs() if entry["role"] not in template_roles})
    assert not missing, f"Named NPC roles missing template coverage: {missing}"


def test_named_npcs_have_required_fields():
    for entry in _load_npcs():
        assert entry.get("name"), f"{entry['id']} missing name"
        assert entry.get("race"), f"{entry['id']} missing race"
        assert entry.get("role"), f"{entry['id']} missing role"
        assert entry.get("faction_alignment"), f"{entry['id']} missing faction alignment"
        personality = entry.get("personality", {})
        assert personality.get("traits"), f"{entry['id']} missing personality traits"
        assert personality.get("motivations"), f"{entry['id']} missing motivations"
        assert personality.get("fears"), f"{entry['id']} missing fears"
        snippets = entry.get("dialogue_snippets", {})
        for field in ("greetings", "farewells", "idle", "quest_related"):
            assert snippets.get(field), f"{entry['id']} missing dialogue_snippets.{field}"
        assert isinstance(entry.get("relationship_modifiers"), dict), (
            f"{entry['id']} missing relationship modifiers"
        )


def test_named_npc_schedules_are_well_formed_and_location_linked():
    valid_locations = _location_ids()
    for entry in _load_npcs():
        schedule = entry.get("schedule")
        assert isinstance(schedule, list) and schedule, f"{entry['id']} missing schedule"
        for block in schedule:
            assert isinstance(block.get("hour"), int), f"{entry['id']} has non-integer schedule hour"
            assert 0 <= block["hour"] <= 23, f"{entry['id']} has invalid schedule hour {block['hour']}"
            assert block.get("activity"), f"{entry['id']} missing schedule activity"
            assert block.get("location"), f"{entry['id']} missing schedule location"
            assert block["location"] in valid_locations, (
                f"{entry['id']} schedule location {block['location']!r} is not a known location id"
            )
