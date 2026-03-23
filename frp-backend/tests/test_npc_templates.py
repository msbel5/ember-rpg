"""
Ember RPG - NPC Template Integration Tests (TDD)

Tests for:
  - Loading NPC templates from data/npcs/npcs.json
  - Structural validation of all NPC fields
  - Dialogue retrieval (consistency and correctness)
  - Relationship modifier logic
"""

import json
import pytest
from pathlib import Path

from engine.core.npc import NPCManager, NPCValidationError, REQUIRED_FIELDS, REQUIRED_DIALOGUE

# Resolve data path relative to test file location
DATA_PATH = Path(__file__).parent.parent / "data" / "npcs" / "npcs.json"
MINIMUM_NPC_COUNT = 20


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def manager():
    """Shared NPCManager instance loaded once for the module."""
    m = NPCManager(data_path=DATA_PATH)
    m.load()
    return m


@pytest.fixture(scope="module")
def raw_npcs():
    """Raw list of NPC dicts from the JSON file."""
    with DATA_PATH.open() as fh:
        data = json.load(fh)
    return data["npcs"]


# ---------------------------------------------------------------------------
# 1. Load tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_file_exists(self):
        assert DATA_PATH.exists(), f"NPC data file not found: {DATA_PATH}"

    def test_load_returns_list(self):
        m = NPCManager(data_path=DATA_PATH)
        result = m.load()
        assert isinstance(result, list)

    def test_load_minimum_count(self, manager):
        npcs = manager.list_npcs()
        assert len(npcs) >= MINIMUM_NPC_COUNT, (
            f"Expected at least {MINIMUM_NPC_COUNT} NPCs, got {len(npcs)}"
        )

    def test_load_exactly_22_npcs(self, manager):
        assert len(manager.list_npcs()) == 22

    def test_load_file_not_found_raises(self):
        m = NPCManager(data_path=Path("/nonexistent/path/npcs.json"))
        with pytest.raises(FileNotFoundError):
            m.load()

    def test_load_invalid_npc_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"npcs": [{"id": "x", "name": "X"}]}))
        m = NPCManager(data_path=bad)
        with pytest.raises(NPCValidationError):
            m.load()

    def test_manager_idempotent_reload(self):
        m = NPCManager(data_path=DATA_PATH)
        first = m.load()
        second = m.load()
        assert len(first) == len(second)


# ---------------------------------------------------------------------------
# 2. Structure validation
# ---------------------------------------------------------------------------

class TestStructure:
    def test_all_npcs_have_required_top_level_fields(self, raw_npcs):
        for npc in raw_npcs:
            missing = REQUIRED_FIELDS - set(npc.keys())
            assert not missing, f"NPC '{npc.get('id')}' missing: {missing}"

    def test_all_ids_are_unique(self, raw_npcs):
        ids = [n["id"] for n in raw_npcs]
        assert len(ids) == len(set(ids)), "Duplicate NPC ids found"

    def test_all_ids_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["id"], str) and len(npc["id"]) > 0

    def test_all_names_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["name"], str) and len(npc["name"]) > 0

    def test_all_races_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["race"], str) and len(npc["race"]) > 0

    def test_all_roles_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["role"], str) and len(npc["role"]) > 0

    def test_all_faction_alignments_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["faction_alignment"], str)

    def test_personality_has_required_keys(self, raw_npcs):
        for npc in raw_npcs:
            p = npc["personality"]
            for key in ("traits", "motivations", "fears"):
                assert key in p, f"NPC '{npc['id']}' personality missing '{key}'"

    def test_personality_traits_is_non_empty_list(self, raw_npcs):
        for npc in raw_npcs:
            traits = npc["personality"]["traits"]
            assert isinstance(traits, list) and len(traits) > 0

    def test_personality_motivations_is_non_empty_list(self, raw_npcs):
        for npc in raw_npcs:
            motivations = npc["personality"]["motivations"]
            assert isinstance(motivations, list) and len(motivations) > 0

    def test_personality_fears_is_non_empty_list(self, raw_npcs):
        for npc in raw_npcs:
            fears = npc["personality"]["fears"]
            assert isinstance(fears, list) and len(fears) > 0

    def test_dialogue_has_required_categories(self, raw_npcs):
        for npc in raw_npcs:
            d = npc["dialogue_snippets"]
            for cat in REQUIRED_DIALOGUE:
                assert cat in d, f"NPC '{npc['id']}' missing dialogue category '{cat}'"

    def test_each_dialogue_category_non_empty(self, raw_npcs):
        for npc in raw_npcs:
            for cat in REQUIRED_DIALOGUE:
                lines = npc["dialogue_snippets"][cat]
                assert isinstance(lines, list) and len(lines) > 0, (
                    f"NPC '{npc['id']}' dialogue '{cat}' is empty"
                )

    def test_dialogue_lines_are_strings(self, raw_npcs):
        for npc in raw_npcs:
            for cat in REQUIRED_DIALOGUE:
                for line in npc["dialogue_snippets"][cat]:
                    assert isinstance(line, str) and len(line) > 0

    def test_relationship_modifiers_is_dict(self, raw_npcs):
        for npc in raw_npcs:
            assert isinstance(npc["relationship_modifiers"], dict)

    def test_relationship_modifiers_non_empty(self, raw_npcs):
        for npc in raw_npcs:
            assert len(npc["relationship_modifiers"]) > 0

    def test_relationship_modifiers_values_are_numeric(self, raw_npcs):
        for npc in raw_npcs:
            for key, val in npc["relationship_modifiers"].items():
                assert isinstance(val, (int, float)), (
                    f"NPC '{npc['id']}' modifier '{key}' = {val!r} is not numeric"
                )

    def test_all_npcs_have_completed_quest_modifier(self, raw_npcs):
        for npc in raw_npcs:
            assert "completed_quest" in npc["relationship_modifiers"], (
                f"NPC '{npc['id']}' missing 'completed_quest' modifier"
            )


# ---------------------------------------------------------------------------
# 3. get() tests
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing_npc(self, manager):
        npc = manager.get("merchant_bram")
        assert npc is not None
        assert npc["name"] == "Bram Holloway"

    def test_get_returns_none_for_unknown(self, manager):
        assert manager.get("does_not_exist") is None

    def test_get_all_npcs_by_id(self, manager):
        for npc in manager.list_npcs():
            fetched = manager.get(npc["id"])
            assert fetched is not None
            assert fetched["id"] == npc["id"]

    def test_get_wizard(self, manager):
        npc = manager.get("wizard_elowen")
        assert npc["race"] == "elf"
        assert npc["role"] == "wizard"

    def test_get_by_role_merchant(self, manager):
        merchants = manager.get_by_role("merchant")
        assert len(merchants) >= 2

    def test_get_by_faction(self, manager):
        watch = manager.get_by_faction("city_watch")
        assert len(watch) >= 2

    def test_get_by_role_returns_correct_roles(self, manager):
        guards = manager.get_by_role("guard")
        for g in guards:
            assert g["role"] == "guard"


# ---------------------------------------------------------------------------
# 4. Dialogue tests
# ---------------------------------------------------------------------------

class TestGetDialogue:
    def test_get_greeting_returns_string(self, manager):
        npc = manager.get("merchant_bram")
        line = manager.get_dialogue(npc, "greetings")
        assert isinstance(line, str) and len(line) > 0

    def test_get_farewell_returns_string(self, manager):
        npc = manager.get("bartender_rynna")
        line = manager.get_dialogue(npc, "farewells")
        assert isinstance(line, str) and len(line) > 0

    def test_get_idle_returns_string(self, manager):
        npc = manager.get("wizard_elowen")
        line = manager.get_dialogue(npc, "idle")
        assert isinstance(line, str) and len(line) > 0

    def test_get_quest_related_returns_string(self, manager):
        npc = manager.get("quest_giver_elder_serafine")
        line = manager.get_dialogue(npc, "quest_related")
        assert isinstance(line, str) and len(line) > 0

    def test_get_dialogue_invalid_category_raises(self, manager):
        npc = manager.get("merchant_bram")
        with pytest.raises(KeyError):
            manager.get_dialogue(npc, "nonexistent_category")

    def test_get_dialogue_first_line_mode(self, manager):
        npc = manager.get("merchant_bram")
        line = manager.get_dialogue(npc, "greetings", random_pick=False)
        assert line == npc["dialogue_snippets"]["greetings"][0]

    def test_get_dialogue_random_is_within_options(self, manager):
        npc = manager.get("rogue_sable")
        options = npc["dialogue_snippets"]["idle"]
        for _ in range(20):
            line = manager.get_dialogue(npc, "idle")
            assert line in options

    def test_all_npcs_all_dialogue_categories(self, manager):
        for npc in manager.list_npcs():
            for cat in REQUIRED_DIALOGUE:
                line = manager.get_dialogue(npc, cat)
                assert isinstance(line, str) and len(line) > 0

    def test_dialogue_consistency_no_empty_lines(self, manager):
        for npc in manager.list_npcs():
            for cat in REQUIRED_DIALOGUE:
                for line in npc["dialogue_snippets"][cat]:
                    assert line.strip() != "", (
                        f"NPC '{npc['id']}' has blank line in '{cat}'"
                    )


# ---------------------------------------------------------------------------
# 5. Relationship modifier tests
# ---------------------------------------------------------------------------

class TestModifyRelationship:
    def test_initial_relationship_is_zero(self, manager):
        # Fresh manager to avoid cross-test state
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        assert m.get_relationship(npc) == 0.0

    def test_positive_modifier_increases_score(self, manager):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        score = m.modify_relationship(npc, "completed_quest")
        assert score > 0

    def test_negative_modifier_decreases_score(self, manager):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        score = m.modify_relationship(npc, "stole_from_shop")
        assert score < 0

    def test_modifier_accumulates(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        m.modify_relationship(npc, "completed_quest")  # +30
        m.modify_relationship(npc, "bought_items")     # +5
        assert m.get_relationship(npc) == pytest.approx(35.0)

    def test_score_clamped_at_100(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("cleric_brother_oswin")
        for _ in range(10):
            m.modify_relationship(npc, "completed_quest")  # +30 each
        assert m.get_relationship(npc) == 100.0

    def test_score_clamped_at_negative_100(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("rogue_sable")
        for _ in range(5):
            m.modify_relationship(npc, "betrayed_to_watch")  # -80 each
        assert m.get_relationship(npc) == -100.0

    def test_unknown_action_raises_key_error(self, manager):
        npc = manager.get("merchant_bram")
        with pytest.raises(KeyError):
            manager.modify_relationship(npc, "nonexistent_action")

    def test_custom_delta_overrides_template(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        score = m.modify_relationship(npc, "completed_quest", custom_delta=50.0)
        assert score == 50.0

    def test_custom_negative_delta(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        score = m.modify_relationship(npc, "completed_quest", custom_delta=-15.0)
        assert score == -15.0

    def test_reset_relationship(self):
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("merchant_bram")
        m.modify_relationship(npc, "completed_quest")
        m.reset_relationship(npc)
        assert m.get_relationship(npc) == 0.0

    def test_completed_quest_modifier_positive_for_all_npcs(self, manager):
        """All NPCs should reward quest completion positively."""
        for npc in manager.list_npcs():
            delta = npc["relationship_modifiers"]["completed_quest"]
            assert delta > 0, f"NPC '{npc['id']}' completed_quest modifier should be positive"

    def test_independent_npc_scores(self):
        """Relationship scores are independent between NPCs."""
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        bram = m.get("merchant_bram")
        dara = m.get("merchant_dara")
        m.modify_relationship(bram, "completed_quest")
        assert m.get_relationship(dara) == 0.0

    def test_relationship_modifiers_applied_correctly(self, manager):
        """Spot-check specific modifier values."""
        m = NPCManager(data_path=DATA_PATH)
        m.load()
        npc = m.get("rogue_sable")
        # betrayed_to_watch = -80
        score = m.modify_relationship(npc, "betrayed_to_watch")
        assert score == -80.0

    def test_list_npcs_count(self, manager):
        assert len(manager.list_npcs()) >= MINIMUM_NPC_COUNT
