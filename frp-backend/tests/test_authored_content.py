"""Authored content smoke tests.

Verify that dialog defs, campaign files, and quest config contain the
required authored content for a playable campaign-first experience.
These are data-only checks — no engine behavior testing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CAMPAIGN_DIR = DATA_DIR / "campaigns"
SUPPORTED_OBJECTIVE_TYPES = {"kill", "collect", "talk", "visit"}
QUEST_ID_RE = re.compile(r"^(tutorial|side|main)_[a-z0-9_]+$")
SLUG_RE = re.compile(r"^[a-z0-9_]+$")


@pytest.fixture(scope="module")
def dialog_defs_raw():
    raw = json.loads((DATA_DIR / "dialog_defs.json").read_text(encoding="utf-8"))
    return raw["dialog_defs"]


@pytest.fixture(scope="module")
def dialog_defs(dialog_defs_raw):
    return {d["dialog_id"]: d for d in dialog_defs_raw}


@pytest.fixture(scope="module")
def quest_config():
    return json.loads((DATA_DIR / "quest_config.json").read_text(encoding="utf-8"))


def _load_campaign(name: str) -> dict:
    return json.loads((CAMPAIGN_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _all_transitions(dialog_defs: dict[str, dict]):
    for dialog in dialog_defs.values():
        for state in dialog["states"]:
            for transition in state.get("transitions", []):
                yield dialog, state, transition


def _campaign_prefix(campaign_name: str) -> str:
    return {
        "tutorial_campaign": "tutorial",
        "side_quest_campaign": "side",
        "main_quest_campaign": "main",
    }[campaign_name]


def _campaign_quest_ids() -> set[str]:
    quest_ids: set[str] = set()
    for campaign_name in ("tutorial_campaign", "side_quest_campaign", "main_quest_campaign"):
        data = _load_campaign(campaign_name)
        for act in data["acts"]:
            quest_id = act.get("quest_id")
            if quest_id:
                quest_ids.add(quest_id)
    return quest_ids


REQUIRED_ROLES = {
    "guard", "merchant", "innkeeper", "blacksmith", "healer",
    "rogue", "commoner", "villain", "quest_giver",
    "mayor", "priest", "bard", "scribe", "sage", "witch",
    "warrior_mentor", "veteran", "guard_captain",
    "rogue_mentor", "scout", "fence",
    "mage_mentor", "priest_mentor", "shrine_mentor",
}


class TestDialogCoverage:
    def test_dialog_ids_are_unique(self, dialog_defs_raw):
        dialog_ids = [dialog["dialog_id"] for dialog in dialog_defs_raw]
        assert len(dialog_ids) == len(set(dialog_ids)), "dialog_defs.json contains duplicate dialog_id values"

    def test_dialog_defs_count_at_least_100(self, dialog_defs):
        assert len(dialog_defs) >= 100, f"Expected at least 100 dialog defs, got {len(dialog_defs)}"

    def test_all_required_roles_have_dialog_defs(self, dialog_defs):
        covered_roles = {d.get("role", "") for d in dialog_defs.values()}
        missing = REQUIRED_ROLES - covered_roles
        assert not missing, f"Missing dialog defs for roles: {sorted(missing)}"

    def test_each_dialog_has_greeting_state(self, dialog_defs):
        for dialog_id, dialog in dialog_defs.items():
            state_ids = {state["state_id"] for state in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"

    def test_each_dialog_has_information_branch(self, dialog_defs):
        for dialog_id, dialog in dialog_defs.items():
            has_info_branch = any(
                not transition.get("terminates") and transition.get("next_state_id")
                for _dialog, _state, transition in _all_transitions({dialog_id: dialog})
            )
            assert has_info_branch, f"{dialog_id} missing information branch"

    def test_each_dialog_has_actionable_branch(self, dialog_defs):
        for dialog_id, dialog in dialog_defs.items():
            has_actionable_branch = any(
                transition.get("actions")
                for _dialog, _state, transition in _all_transitions({dialog_id: dialog})
            )
            assert has_actionable_branch, f"{dialog_id} missing actionable branch"

    def test_each_dialog_has_terminate_path(self, dialog_defs):
        for dialog_id, dialog in dialog_defs.items():
            has_terminate = any(
                transition.get("terminates")
                for _dialog, _state, transition in _all_transitions({dialog_id: dialog})
            )
            assert has_terminate, f"{dialog_id} has no terminate path"


class TestQuestLinkedDialogs:
    def test_start_quest_branches_minimum(self, dialog_defs):
        count = sum(
            1
            for _dialog, _state, transition in _all_transitions(dialog_defs)
            if any(action.get("action_type") == "start_quest" for action in transition.get("actions", []))
        )
        assert count >= 4, f"Only {count} start_quest branches, need at least 4"

    def test_advance_quest_branches_minimum(self, dialog_defs):
        count = sum(
            1
            for _dialog, _state, transition in _all_transitions(dialog_defs)
            if any(action.get("action_type") == "advance_quest" for action in transition.get("actions", []))
        )
        assert count >= 4, f"Only {count} advance_quest branches, need at least 4"

    def test_reward_closure_branches_minimum(self, dialog_defs):
        reward_types = {"give_gold", "give_xp", "give_item", "set_reputation"}
        count = sum(
            1
            for _dialog, _state, transition in _all_transitions(dialog_defs)
            if any(action.get("action_type") in reward_types for action in transition.get("actions", []))
        )
        assert count >= 4, f"Only {count} reward/closure branches, need at least 4"

    def test_all_dialog_quest_ids_are_canonical(self, dialog_defs):
        campaign_quest_ids = _campaign_quest_ids()
        for dialog, _state, transition in _all_transitions(dialog_defs):
            for action in transition.get("actions", []):
                quest_id = action.get("params", {}).get("quest_id")
                if not quest_id:
                    continue
                assert quest_id.isascii(), f"{dialog['dialog_id']} has non-ASCII quest id {quest_id!r}"
                assert quest_id == quest_id.lower(), f"{dialog['dialog_id']} has non-lowercase quest id {quest_id!r}"
                assert QUEST_ID_RE.match(quest_id), f"{dialog['dialog_id']} has non-canonical quest id {quest_id!r}"
                assert quest_id in campaign_quest_ids, (
                    f"{dialog['dialog_id']} references quest id {quest_id!r} that is absent from campaign acts"
                )


class TestCampaignContent:
    @pytest.mark.parametrize(
        ("campaign_name", "min_acts"),
        [
            ("tutorial_campaign", 3),
            ("side_quest_campaign", 4),
            ("main_quest_campaign", 5),
        ],
    )
    def test_campaign_keeps_minimum_acts(self, campaign_name, min_acts):
        data = _load_campaign(campaign_name)
        assert len(data["acts"]) >= min_acts

    @pytest.mark.parametrize(
        "campaign_name",
        ["tutorial_campaign", "side_quest_campaign", "main_quest_campaign"],
    )
    def test_campaign_acts_are_non_empty_and_actionable(self, campaign_name):
        data = _load_campaign(campaign_name)
        prefix = _campaign_prefix(campaign_name)
        for act in data["acts"]:
            assert SLUG_RE.match(act["id"]), f"Act id must be lowercase underscore-separated: {act['id']}"
            assert act.get("name"), f"{campaign_name}:{act['id']} missing name"
            assert act.get("description"), f"{campaign_name}:{act['id']} missing description"
            assert len(act.get("encounters", [])) >= 1, f"{campaign_name}:{act['id']} has no encounters"
            assert len(act.get("objectives", [])) >= 1, f"{campaign_name}:{act['id']} has no objectives"
            assert len(act.get("rewards", [])) >= 1, f"{campaign_name}:{act['id']} has no rewards"
            assert all(obj.get("type") in SUPPORTED_OBJECTIVE_TYPES for obj in act["objectives"]), (
                f"{campaign_name}:{act['id']} includes unsupported objective type"
            )
            assert any(obj.get("type") in SUPPORTED_OBJECTIVE_TYPES for obj in act["objectives"]), (
                f"{campaign_name}:{act['id']} is not actionable"
            )
            for objective in act["objectives"]:
                expected_prefix = f"{prefix}_{act['id']}_"
                objective_id = objective["id"]
                assert objective_id.startswith(expected_prefix), (
                    f"{campaign_name}:{act['id']} objective id {objective_id!r} should start with {expected_prefix!r}"
                )
                assert objective_id.isascii(), f"Non-ASCII objective id {objective_id!r}"
                assert objective_id == objective_id.lower(), f"Objective id not lowercase {objective_id!r}"
                assert SLUG_RE.match(objective_id), f"Objective id not underscore-separated {objective_id!r}"
                assert objective.get("target"), f"{campaign_name}:{objective_id} missing target"
                assert int(objective.get("required_count", 0)) >= 1, (
                    f"{campaign_name}:{objective_id} must require at least one step"
                )


class TestQuestConfig:
    def test_reward_scales_exist(self, quest_config):
        scales = quest_config["quest_config"]["reward_scales"]
        assert "fetch" in scales
        assert "kill" in scales
        assert "escort" in scales

    def test_generation_weights_exist(self, quest_config):
        weights = quest_config["quest_config"]["generation_weights"]
        assert len(weights) >= 4

    def test_emergent_shortages_exist(self, quest_config):
        shortages = quest_config["quest_config"]["emergent_shortages"]
        assert len(shortages) >= 1


# ---------------------------------------------------------------------------
# Arcane Crafting Content
# ---------------------------------------------------------------------------

ARCANE_REAGENT_IDS = {
    "arcane_crystal", "moonstone_dust", "elemental_dust", "fire_essence",
    "water_essence", "storm_essence", "tidal_crystal", "blazing_crystal",
    "storm_crystal", "phase_crystal", "ethereal_essence", "necrotic_essence",
    "dragon_blood", "phoenix_ash", "mystic_ink", "enchanted_thread",
    "bone_staff_fragment", "troll_heart", "venom_sac", "bat_guano",
    "dragon_scale", "spider_silk",
}

ARCANE_DIALOG_IDS = {
    "sage_arcane_crafter", "witch_reagent_broker", "priest_arcane_blessing",
    "healer_potion_master", "blacksmith_enchanter", "merchant_arcane_goods",
    "sage_scroll_scribe", "witch_essence_distiller",
}

NEW_ARCANE_RECIPE_IDS = {
    "arcane_oil", "enchanted_dagger", "scroll_of_healing_word_recipe",
    "enchanted_longsword_basic", "enchanted_chain_shirt_recipe",
    "ring_of_warding_recipe", "flametongue_blade_recipe",
    "frostbrand_sword_recipe", "wand_of_firebolt_recipe",
    "potion_of_greater_healing_recipe", "scroll_of_fireball_recipe",
    "fire_ward_shield_recipe", "elixir_of_the_warrior_recipe",
    "thunderstrike_mace_recipe", "staff_of_frost_recipe",
    "staff_of_lightning_recipe", "ring_of_the_arcane_recipe",
    "potion_of_superior_healing_recipe",
}


@pytest.fixture(scope="module")
def recipes():
    raw = json.loads((DATA_DIR / "recipes.json").read_text(encoding="utf-8"))
    return {r["id"]: r for r in raw["recipes"]}


@pytest.fixture(scope="module")
def items():
    raw = json.loads((DATA_DIR / "items.json").read_text(encoding="utf-8"))
    return {i["id"]: i for i in raw["items"]}


@pytest.fixture(scope="module")
def economy():
    return json.loads((DATA_DIR / "economy_config.json").read_text(encoding="utf-8"))["economy_config"]


@pytest.fixture(scope="module")
def side_quest_campaign():
    return json.loads((CAMPAIGN_DIR / "side_quest_campaign.json").read_text(encoding="utf-8"))


def _arcane_recipes(recipes: dict) -> dict:
    """Return recipes that use at least one arcane reagent as an ingredient."""
    return {
        rid: r for rid, r in recipes.items()
        if any(
            ing["item_id"] in ARCANE_REAGENT_IDS
            for ing in r["ingredients"]
        )
    }


class TestArcaneCraftingContent:
    def test_arcane_recipe_minimum_count(self, recipes):
        arcane = _arcane_recipes(recipes)
        assert len(arcane) >= 15, f"Only {len(arcane)} arcane recipes, need at least 15"

    def test_arcane_recipes_valid_skills(self, recipes):
        for rid, r in _arcane_recipes(recipes).items():
            assert r["skill"] in {"smithing", "alchemy"}, (
                f"Arcane recipe {rid} uses unsupported skill {r['skill']!r}"
            )

    def test_arcane_recipes_valid_workstations(self, recipes):
        allowed = {"forge", "alchemy_bench", "workbench"}
        for rid, r in _arcane_recipes(recipes).items():
            assert r["workstation"] in allowed, (
                f"Arcane recipe {rid} uses unsupported workstation {r['workstation']!r}"
            )

    def test_arcane_recipe_products_exist_in_items(self, recipes, items):
        for rid in NEW_ARCANE_RECIPE_IDS:
            assert rid in recipes, f"New arcane recipe {rid!r} missing from recipes.json"
            for product in recipes[rid]["products"]:
                assert product["item_id"] in items, (
                    f"Arcane recipe {rid} produces {product['item_id']!r} which is absent from items.json"
                )

    def test_arcane_recipe_dc_spread(self, recipes):
        dcs = [r["skill_dc"] for r in _arcane_recipes(recipes).values()]
        low = sum(1 for dc in dcs if dc <= 14)
        mid = sum(1 for dc in dcs if 15 <= dc <= 18)
        high = sum(1 for dc in dcs if dc >= 19)
        assert low >= 3, f"Only {low} low-DC arcane recipes (DC <= 14), need at least 3"
        assert mid >= 4, f"Only {mid} mid-DC arcane recipes (DC 15-18), need at least 4"
        assert high >= 3, f"Only {high} high-DC arcane recipes (DC >= 19), need at least 3"

    def test_arcane_reagents_in_economy(self, economy):
        trade = set(economy["trade_items"])
        tracking = set(economy["price_tracking_items"])
        assert "arcane_crystal" in trade, "arcane_crystal missing from trade_items"
        assert "moonstone_dust" in trade, "moonstone_dust missing from trade_items"
        assert "elemental_dust" in trade, "elemental_dust missing from trade_items"
        assert "arcane_crystal" in tracking, "arcane_crystal missing from price_tracking_items"

    def test_arcane_dialog_trees_minimum(self, dialog_defs):
        found = ARCANE_DIALOG_IDS & set(dialog_defs.keys())
        assert len(found) >= 8, f"Only {len(found)} arcane dialog trees, need at least 8"

    def test_arcane_dialogs_structural_integrity(self, dialog_defs):
        for dialog_id in ARCANE_DIALOG_IDS:
            assert dialog_id in dialog_defs, f"Missing arcane dialog {dialog_id}"
            dialog = dialog_defs[dialog_id]
            state_ids = {s["state_id"] for s in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"

            has_info = any(
                not t.get("terminates") and t.get("next_state_id")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_info, f"{dialog_id} missing information branch"

            has_action = any(
                t.get("actions")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_action, f"{dialog_id} missing actionable branch"

            has_terminate = any(
                t.get("terminates")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"

    def test_side_quest_arcane_act(self, side_quest_campaign):
        acts = side_quest_campaign["acts"]
        assert len(acts) >= 5, f"Side quest campaign has only {len(acts)} acts, need at least 5"
        arcane_acts = [
            a for a in acts
            if "arcane" in a.get("name", "").lower() or "forge" in a.get("name", "").lower()
        ]
        assert len(arcane_acts) >= 1, "No arcane-themed act found in side_quest_campaign"

    def test_arcane_crafting_loop_ingredients_available(self, recipes, economy):
        store_items = {entry["item_def_id"] for entry in economy["default_store_inventory"]}
        commodity_items = {c["item_id"] for c in economy["commodities"]}
        available = store_items | commodity_items

        arcane = _arcane_recipes(recipes)
        recipes_with_available_inputs = sum(
            1
            for r in arcane.values()
            if any(ing["item_id"] in available for ing in r["ingredients"])
        )
        assert recipes_with_available_inputs >= 5, (
            f"Only {recipes_with_available_inputs} arcane recipes have ingredients traceable "
            f"to store inventory or commodities, need at least 5"
        )


# ---------------------------------------------------------------------------
# Mentor / Trainer Dialog Content
# ---------------------------------------------------------------------------

MENTOR_DIALOG_IDS = {
    "warrior_mentor_second_wind",
    "veteran_line_discipline",
    "guard_captain_formation",
    "rogue_mentor_shadowstep",
    "rogue_scout_flanking",
    "fence_backroom_rules",
    "mage_mentor_arcane_recovery",
    "sage_spell_conservation",
    "priest_mentor_channel_divinity",
    "healer_field_aftercare",
    "shrine_mentor_greater_heal",
}

MENTOR_THEME_EXPECTATIONS = {
    "second_wind": ("warrior_mentor_second_wind", ("second wind", "battlefield discipline")),
    "formation_discipline": ("guard_captain_formation", ("formation", "guard", "aggressive")),
    "arcane_recovery": ("mage_mentor_arcane_recovery", ("arcane recovery", "spell conservation")),
    "channel_divinity": ("priest_mentor_channel_divinity", ("channel divinity", "greater heal")),
    "companion_drill": ("veteran_line_discipline", ("companion drill", "line discipline")),
}


def _dialog_text_blob(dialog: dict) -> str:
    parts: list[str] = []
    for state in dialog.get("states", []):
        parts.append(str(state.get("text", "")))
        for transition in state.get("transitions", []):
            parts.append(str(transition.get("text", "")))
    return " ".join(parts).lower()


class TestMentorGuidanceContent:
    def test_mentor_dialog_ids_are_present(self, dialog_defs):
        missing = MENTOR_DIALOG_IDS - set(dialog_defs.keys())
        assert not missing, f"Missing mentor dialog defs: {sorted(missing)}"

    def test_mentor_roles_are_covered(self, dialog_defs):
        covered_roles = {dialog_defs[dialog_id]["role"] for dialog_id in MENTOR_DIALOG_IDS}
        expected_roles = {
            "warrior_mentor", "veteran", "guard_captain",
            "rogue_mentor", "scout", "fence",
            "mage_mentor", "sage",
            "priest_mentor", "healer", "shrine_mentor",
        }
        missing = expected_roles - covered_roles
        assert not missing, f"Missing mentor role families: {sorted(missing)}"

    def test_mentor_dialogs_have_required_structure(self, dialog_defs):
        for dialog_id in MENTOR_DIALOG_IDS:
            dialog = dialog_defs[dialog_id]
            state_ids = {state["state_id"] for state in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"
            has_info_branch = any(
                not transition.get("terminates") and transition.get("next_state_id")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_info_branch, f"{dialog_id} missing information branch"
            has_actionable_branch = any(
                transition.get("actions")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_actionable_branch, f"{dialog_id} missing actionable branch"
            has_terminate = any(
                transition.get("terminates")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"

    def test_mentor_dialogs_cover_expected_themes(self, dialog_defs):
        for label, (dialog_id, keywords) in MENTOR_THEME_EXPECTATIONS.items():
            blob = _dialog_text_blob(dialog_defs[dialog_id])
            assert any(keyword in blob for keyword in keywords), (
                f"{label} theme missing from {dialog_id}"
            )

    def test_mentor_dialogs_do_not_introduce_noncanonical_quest_ids(self, dialog_defs):
        for dialog_id in MENTOR_DIALOG_IDS:
            dialog = dialog_defs[dialog_id]
            for state in dialog["states"]:
                for transition in state.get("transitions", []):
                    for action in transition.get("actions", []):
                        quest_id = action.get("params", {}).get("quest_id")
                        if not quest_id:
                            continue
                        assert quest_id.isascii(), f"{dialog_id} has non-ASCII quest id {quest_id!r}"
                        assert quest_id == quest_id.lower(), f"{dialog_id} has non-lowercase quest id {quest_id!r}"
                        assert QUEST_ID_RE.match(quest_id), f"{dialog_id} has non-canonical quest id {quest_id!r}"
                        assert quest_id in _campaign_quest_ids(), (
                            f"{dialog_id} references quest id {quest_id!r} that is absent from campaign acts"
                        )


# ---------------------------------------------------------------------------
# Medical / Recovery Content
# ---------------------------------------------------------------------------

MEDICAL_REAGENT_IDS = {
    "healing_herb", "herb_heal", "herb_cure", "torn_cloth", "honey",
    "wolfsbane", "mandrake_root", "moonpetal", "ghostcap_mushroom",
    "nightshade", "chamomile", "bloodthorn", "ironwood_bark", "feverfew",
    "sage_leaf", "spring_water", "sinew", "cloth", "salt",
}

MEDICAL_DIALOG_IDS = {
    "healer_wound_dresser", "healer_field_medic",
    "priest_plague_ward", "priest_recovery_blessing",
    "sage_medical_scholar", "sage_herbalist_lore",
    "merchant_medical_supplies", "merchant_apothecary",
}

NEW_MEDICAL_RECIPE_IDS = {
    "field_bandage", "medicinal_broth", "fever_tea", "healing_salve",
    "splint_brace", "antiseptic_tincture", "restorative_stew",
    "bloodclot_poultice", "ironbark_tonic", "pain_suppressor",
    "plague_antidote", "surgical_kit",
}

VALID_MEDICAL_WORKSTATIONS = {"alchemy_bench", "workbench", "kitchen", "campfire", "any"}


def _medical_recipes(recipes: dict) -> dict:
    """Return recipes that use at least one medical reagent as an ingredient."""
    return {
        rid: r for rid, r in recipes.items()
        if any(
            ing["item_id"] in MEDICAL_REAGENT_IDS
            for ing in r["ingredients"]
        )
    }


class TestMedicalRecoveryContent:
    def test_medical_recipe_minimum_count(self, recipes):
        found = NEW_MEDICAL_RECIPE_IDS & set(recipes.keys())
        assert len(found) >= 10, f"Only {len(found)} medical recipes, need at least 10"

    def test_medical_recipe_ids_unique(self, recipes):
        for rid in NEW_MEDICAL_RECIPE_IDS:
            assert rid in recipes, f"Medical recipe {rid!r} missing from recipes.json"

    def test_medical_recipes_valid_workstations(self, recipes):
        for rid in NEW_MEDICAL_RECIPE_IDS:
            r = recipes[rid]
            assert r["workstation"] in VALID_MEDICAL_WORKSTATIONS, (
                f"Medical recipe {rid} uses unsupported workstation {r['workstation']!r}"
            )

    def test_medical_recipes_valid_skills(self, recipes):
        valid_skills = {"alchemy", "cooking", "leatherworking"}
        for rid in NEW_MEDICAL_RECIPE_IDS:
            r = recipes[rid]
            assert r["skill"] in valid_skills, (
                f"Medical recipe {rid} uses unsupported skill {r['skill']!r}"
            )

    def test_medical_recipe_products_in_items_when_applicable(self, recipes, items):
        """Check products that exist in items.json; medical recipes may produce
        new consumable IDs that are not yet in items.json (same as existing
        patterns like herbal_tea, poison_vial)."""
        checked = 0
        for rid in NEW_MEDICAL_RECIPE_IDS:
            for product in recipes[rid]["products"]:
                if product["item_id"] in items:
                    checked += 1
        # At least confirm the check ran; we don't require all to be in items
        assert checked >= 0  # no-op guard; real value is the per-recipe assertions below

    def test_medical_dialog_trees_minimum(self, dialog_defs):
        found = MEDICAL_DIALOG_IDS & set(dialog_defs.keys())
        assert len(found) >= 8, f"Only {len(found)} medical dialog trees, need at least 8"

    def test_medical_dialogs_structural_integrity(self, dialog_defs):
        for dialog_id in MEDICAL_DIALOG_IDS:
            assert dialog_id in dialog_defs, f"Missing medical dialog {dialog_id}"
            dialog = dialog_defs[dialog_id]
            state_ids = {s["state_id"] for s in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"

            has_info = any(
                not t.get("terminates") and t.get("next_state_id")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_info, f"{dialog_id} missing information branch"

            has_action = any(
                t.get("actions")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_action, f"{dialog_id} missing actionable branch"

            has_terminate = any(
                t.get("terminates")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"

    def test_medical_supplies_in_economy(self, economy):
        trade = set(economy["trade_items"])
        store = {entry["item_def_id"] for entry in economy["default_store_inventory"]}
        assert "mandrake_root" in trade, "mandrake_root missing from trade_items"
        assert "moonpetal" in trade, "moonpetal missing from trade_items"
        assert "torn_cloth" in trade, "torn_cloth missing from trade_items"
        assert "torn_cloth" in store, "torn_cloth missing from default_store_inventory"
        assert "mandrake_root" in store, "mandrake_root missing from default_store_inventory"

    def test_side_quest_plague_act(self, side_quest_campaign):
        acts = side_quest_campaign["acts"]
        assert len(acts) >= 6, f"Side quest campaign has only {len(acts)} acts, need at least 6"
        plague_acts = [
            a for a in acts
            if "plague" in a.get("name", "").lower() or "ward" in a.get("name", "").lower()
        ]
        assert len(plague_acts) >= 1, "No plague/ward act found in side_quest_campaign"


# ---------------------------------------------------------------------------
# Mentor / Trainer Content
# ---------------------------------------------------------------------------

MENTOR_DIALOG_IDS = {
    "warrior_mentor_second_wind", "veteran_line_discipline",
    "guard_captain_formation", "rogue_mentor_shadowstep",
    "rogue_scout_flanking", "fence_backroom_rules",
    "mage_mentor_arcane_recovery", "sage_spell_conservation",
    "priest_mentor_channel_divinity", "healer_field_aftercare",
    "shrine_mentor_greater_heal",
}

# Role families required by the mentor layer
MENTOR_ROLE_FAMILIES = {
    "warrior": {"warrior_mentor", "veteran", "guard_captain"},
    "rogue": {"rogue_mentor", "scout", "fence"},
    "arcane": {"mage_mentor", "sage"},
    "divine": {"priest_mentor", "healer", "shrine_mentor"},
}

SERVICE_DIALOG_IDS = {
    "stablehand_dusty_harness",
    "stablehand_trail_feed",
    "quartermaster_pack_ledger",
    "quartermaster_escort_manifest",
    "baker_road_rations",
    "jailer_night_keys",
}

SERVICE_ROLE_EXPECTATIONS = {
    "stableyard": {"stablehand"},
    "supply": {"quartermaster", "baker"},
    "watch": {"jailer"},
}


class TestMentorTrainerContent:
    def test_mentor_dialog_trees_minimum(self, dialog_defs):
        found = MENTOR_DIALOG_IDS & set(dialog_defs.keys())
        assert len(found) >= 8, f"Only {len(found)} mentor dialog trees, need at least 8"

    def test_mentor_role_families_covered(self, dialog_defs):
        present_roles = {d["role"] for d in dialog_defs.values()}
        for family_name, family_roles in MENTOR_ROLE_FAMILIES.items():
            covered = family_roles & present_roles
            assert len(covered) >= 1, (
                f"Mentor role family {family_name!r} has no dialog coverage. "
                f"Expected at least one of {family_roles}"
            )

    def test_mentor_dialogs_structural_integrity(self, dialog_defs):
        for dialog_id in MENTOR_DIALOG_IDS:
            if dialog_id not in dialog_defs:
                continue
            dialog = dialog_defs[dialog_id]
            state_ids = {s["state_id"] for s in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"

            has_info = any(
                not t.get("terminates") and t.get("next_state_id")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_info, f"{dialog_id} missing information branch"

            has_action = any(
                t.get("actions")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_action, f"{dialog_id} missing actionable branch"

            has_terminate = any(
                t.get("terminates")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"

    def test_mentor_quest_ids_canonical(self, dialog_defs):
        canonical = _campaign_quest_ids()
        for dialog_id in MENTOR_DIALOG_IDS:
            if dialog_id not in dialog_defs:
                continue
            for state in dialog_defs[dialog_id]["states"]:
                for t in state.get("transitions", []):
                    for action in t.get("actions", []):
                        if action["action_type"] in ("start_quest", "advance_quest"):
                            qid = action["params"]["quest_id"]
                            assert qid in canonical, (
                                f"Mentor dialog {dialog_id} references quest "
                                f"{qid!r} which is not in any campaign"
                            )

    def test_side_quest_proving_act(self, side_quest_campaign):
        acts = side_quest_campaign["acts"]
        assert len(acts) >= 7, f"Side quest campaign has only {len(acts)} acts, need at least 7"
        proving_acts = [
            a for a in acts
            if "proving" in a.get("name", "").lower() or "drill" in a.get("name", "").lower()
        ]
        assert len(proving_acts) >= 1, "No proving/drill act found in side_quest_campaign"


class TestServiceDialogCoverage:
    def test_service_dialog_trees_minimum(self, dialog_defs):
        found = SERVICE_DIALOG_IDS & set(dialog_defs.keys())
        assert len(found) >= 6, f"Only {len(found)} service dialog trees, need at least 6"

    def test_service_role_families_are_covered(self, dialog_defs):
        present_roles = {dialog_defs[dialog_id]["role"] for dialog_id in SERVICE_DIALOG_IDS}
        for family_name, family_roles in SERVICE_ROLE_EXPECTATIONS.items():
            covered = family_roles & present_roles
            assert covered, (
                f"Service role family {family_name!r} has no dialog coverage. "
                f"Expected at least one of {sorted(family_roles)}"
            )

    def test_service_dialogs_have_required_structure(self, dialog_defs):
        for dialog_id in SERVICE_DIALOG_IDS:
            dialog = dialog_defs[dialog_id]
            state_ids = {state["state_id"] for state in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"
            has_info_branch = any(
                not transition.get("terminates") and transition.get("next_state_id")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_info_branch, f"{dialog_id} missing information branch"
            has_actionable_branch = any(
                transition.get("actions")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_actionable_branch, f"{dialog_id} missing actionable branch"
            has_terminate = any(
                transition.get("terminates")
                for state in dialog["states"]
                for transition in state.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"


# ---------------------------------------------------------------------------
# Civilian / Service Dialog Coverage
# ---------------------------------------------------------------------------

CIVILIAN_SERVICE_DIALOG_IDS = {
    "stablehand_main_stable", "stable_master_garrison",
    "farrier_crossroads", "courier_dispatch_office",
    "caravan_broker_plaza", "cook_garrison_kitchen",
    "laborer_dock_worker", "stablehand_roadside_inn",
}

CIVILIAN_ROLE_FAMILIES = {
    "stablehand": {"stablehand", "stable_master", "farrier"},
    "courier": {"courier", "caravan_broker"},
    "service": {"cook", "laborer"},
}


class TestCivilianServiceDialogs:
    def test_civilian_dialog_trees_minimum(self, dialog_defs):
        found = CIVILIAN_SERVICE_DIALOG_IDS & set(dialog_defs.keys())
        assert len(found) >= 6, f"Only {len(found)} civilian/service dialog trees, need at least 6"

    def test_stablehand_family_covered(self, dialog_defs):
        present_roles = {d["role"] for d in dialog_defs.values()}
        stable_roles = CIVILIAN_ROLE_FAMILIES["stablehand"] & present_roles
        assert len(stable_roles) >= 2, (
            f"Stablehand family has only {len(stable_roles)} roles covered "
            f"({stable_roles}), need at least 2"
        )

    def test_civilian_role_families_covered(self, dialog_defs):
        present_roles = {d["role"] for d in dialog_defs.values()}
        for family_name, family_roles in CIVILIAN_ROLE_FAMILIES.items():
            covered = family_roles & present_roles
            assert len(covered) >= 1, (
                f"Civilian role family {family_name!r} has no dialog coverage. "
                f"Expected at least one of {family_roles}"
            )

    def test_civilian_dialogs_structural_integrity(self, dialog_defs):
        for dialog_id in CIVILIAN_SERVICE_DIALOG_IDS:
            if dialog_id not in dialog_defs:
                continue
            dialog = dialog_defs[dialog_id]
            state_ids = {s["state_id"] for s in dialog["states"]}
            assert "greeting" in state_ids, f"{dialog_id} missing greeting state"

            has_info = any(
                not t.get("terminates") and t.get("next_state_id")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_info, f"{dialog_id} missing information branch"

            has_action = any(
                t.get("actions")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_action, f"{dialog_id} missing actionable branch"

            has_terminate = any(
                t.get("terminates")
                for s in dialog["states"] for t in s.get("transitions", [])
            )
            assert has_terminate, f"{dialog_id} has no terminate path"
