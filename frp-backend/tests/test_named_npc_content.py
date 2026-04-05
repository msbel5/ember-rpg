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

# Authored-only NPC roles that are valid named NPC records without
# template backing (hand-authored, not generated from templates).
AUTHORED_ONLY_ROLES = {"stablehand"}
ROLE_TEMPLATE_ALIASES = {
    "stablehand": "commoner",
}

KEY_LOCATION_ROLE_PAIRS = {
    ("river_port", "guard"),
    ("river_port", "priest"),
    ("river_port", "healer"),
    ("river_port", "alchemist"),
    ("river_port", "innkeeper"),
    ("hill_town", "merchant"),
    ("hill_town", "innkeeper"),
    ("merchant_camp", "guard"),
    ("merchant_camp", "commoner"),
    ("coastal_cliffs", "scout"),
    ("border_fort", "ranger"),
    ("forest_haven", "blacksmith"),
}

SETTLEMENT_LOCATIONS = [
    "harbor_town", "mountain_hold", "forest_haven", "desert_outpost",
    "swamp_village", "plains_crossing", "coastal_fort", "mining_camp",
    "temple_sanctuary", "frontier_post",
]

REQUIRED_SETTLEMENT_ROLES = {
    "guard", "innkeeper", "blacksmith", "priest", "healer",
    "merchant", "sage", "scout", "stablehand", "commoner",
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


def _named_npc_location_role_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for entry in _load_npcs():
        role = entry["role"]
        for block in entry["schedule"]:
            pairs.add((block["location"], role))
    return pairs


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
    missing = sorted(
        {
            entry["role"]
            for entry in _load_npcs()
            if entry["role"] not in template_roles
            and ROLE_TEMPLATE_ALIASES.get(entry["role"]) not in template_roles
        }
    )
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


def test_named_npc_corpus_covers_key_social_location_role_pairs():
    pairs = _named_npc_location_role_pairs()
    missing = sorted(pair for pair in KEY_LOCATION_ROLE_PAIRS if pair not in pairs)
    assert not missing, f"Missing authored location/role pairs: {missing}"


def test_settlement_role_coverage_complete():
    """Every settlement must have all 10 required social roles covered."""
    pairs = _named_npc_location_role_pairs()
    gaps = []
    for loc in SETTLEMENT_LOCATIONS:
        for role in REQUIRED_SETTLEMENT_ROLES:
            if (loc, role) not in pairs:
                gaps.append((loc, role))
    assert not gaps, f"Settlement role coverage gaps ({len(gaps)}): {gaps}"


def test_named_npcs_count_at_least_250():
    assert len(_load_npcs()) >= 250, "Expected at least 250 named NPCs after normalization"


def test_no_unsupported_schema_fields():
    allowed = {"id", "name", "race", "role", "faction_alignment",
               "personality", "dialogue_snippets", "relationship_modifiers", "schedule"}
    for entry in _load_npcs():
        extra = set(entry.keys()) - allowed
        assert not extra, f"NPC {entry['id']} has unsupported fields: {extra}"


def test_stablehand_coverage_across_all_settlements():
    """Stablehand role must be present in every settlement."""
    pairs = _named_npc_location_role_pairs()
    missing = [loc for loc in SETTLEMENT_LOCATIONS if (loc, "stablehand") not in pairs]
    assert not missing, f"Stablehand missing from settlements: {missing}"
