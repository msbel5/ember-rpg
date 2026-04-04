"""Authored content smoke tests.

Verify that dialog defs, campaign files, and quest config contain the
required content for a playable campaign-first experience. These are
data-only checks — no engine behavior testing.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CAMPAIGN_DIR = DATA_DIR / "campaigns"


@pytest.fixture(scope="module")
def dialog_defs():
    raw = json.loads((DATA_DIR / "dialog_defs.json").read_text(encoding="utf-8"))
    return {d["dialog_id"]: d for d in raw["dialog_defs"]}


@pytest.fixture(scope="module")
def quest_config():
    return json.loads((DATA_DIR / "quest_config.json").read_text(encoding="utf-8"))


def _load_campaign(name):
    return json.loads((CAMPAIGN_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Dialog role coverage
# ---------------------------------------------------------------------------

REQUIRED_ROLES = {
    "guard", "merchant", "innkeeper", "blacksmith", "healer",
    "rogue", "commoner", "villain", "quest_giver",
    "mayor", "priest", "bard", "scribe", "sage", "witch",
}


class TestDialogRoleCoverage:
    def test_all_required_roles_have_dialog_defs(self, dialog_defs):
        covered_roles = {d.get("role", "") for d in dialog_defs.values()}
        missing = REQUIRED_ROLES - covered_roles
        assert not missing, f"Missing dialog defs for roles: {missing}"

    def test_each_dialog_has_greeting_state(self, dialog_defs):
        for did, d in dialog_defs.items():
            state_ids = {s["state_id"] for s in d["states"]}
            assert "greeting" in state_ids, f"{did} missing greeting state"

    def test_each_dialog_has_at_least_one_info_branch(self, dialog_defs):
        for did, d in dialog_defs.items():
            assert len(d["states"]) >= 2, f"{did} needs at least 2 states (greeting + info)"

    def test_each_dialog_has_terminate_path(self, dialog_defs):
        for did, d in dialog_defs.items():
            has_terminate = False
            for state in d["states"]:
                for t in state.get("transitions", []):
                    if t.get("terminates"):
                        has_terminate = True
                        break
                if has_terminate:
                    break
            assert has_terminate, f"{did} has no terminate path"


# ---------------------------------------------------------------------------
# 2. Quest-connected dialog content
# ---------------------------------------------------------------------------

class TestQuestLinkedDialogs:
    def _all_transitions(self, dialog_defs):
        for d in dialog_defs.values():
            for state in d["states"]:
                for t in state.get("transitions", []):
                    yield d["dialog_id"], t

    def test_at_least_two_start_quest_branches(self, dialog_defs):
        count = 0
        for _did, t in self._all_transitions(dialog_defs):
            for action in t.get("actions", []):
                if action.get("action_type") == "start_quest":
                    count += 1
        assert count >= 2, f"Only {count} start_quest branches, need at least 2"

    def test_at_least_two_advance_quest_branches(self, dialog_defs):
        count = 0
        for _did, t in self._all_transitions(dialog_defs):
            for action in t.get("actions", []):
                if action.get("action_type") == "advance_quest":
                    count += 1
        assert count >= 2, f"Only {count} advance_quest branches, need at least 2"

    def test_at_least_two_reward_closure_branches(self, dialog_defs):
        reward_types = {"give_gold", "give_xp", "give_item", "set_reputation"}
        count = 0
        for _did, t in self._all_transitions(dialog_defs):
            action_types = {a.get("action_type") for a in t.get("actions", [])}
            if action_types & reward_types:
                count += 1
        assert count >= 2, f"Only {count} reward/closure branches, need at least 2"

    def test_quest_ids_are_stable_ascii(self, dialog_defs):
        for _did, t in self._all_transitions(dialog_defs):
            for action in t.get("actions", []):
                qid = action.get("params", {}).get("quest_id")
                if qid:
                    assert qid.isascii(), f"Quest id not ASCII: {qid}"
                    assert " " not in qid, f"Quest id has spaces: {qid}"


# ---------------------------------------------------------------------------
# 3. Campaign content
# ---------------------------------------------------------------------------

class TestTutorialCampaign:
    def test_has_at_least_3_acts(self):
        data = _load_campaign("tutorial_campaign")
        assert len(data["acts"]) >= 3

    def test_each_act_has_objectives(self):
        data = _load_campaign("tutorial_campaign")
        for act in data["acts"]:
            assert len(act["objectives"]) >= 1, f"{act['id']} has no objectives"

    def test_each_act_has_rewards(self):
        data = _load_campaign("tutorial_campaign")
        for act in data["acts"]:
            assert len(act["rewards"]) >= 1, f"{act['id']} has no rewards"


class TestSideQuestCampaign:
    def test_has_at_least_4_acts(self):
        data = _load_campaign("side_quest_campaign")
        assert len(data["acts"]) >= 4

    def test_each_act_has_objectives(self):
        data = _load_campaign("side_quest_campaign")
        for act in data["acts"]:
            assert len(act["objectives"]) >= 1, f"{act['id']} has no objectives"

    def test_each_act_has_rewards(self):
        data = _load_campaign("side_quest_campaign")
        for act in data["acts"]:
            assert len(act["rewards"]) >= 1, f"{act['id']} has no rewards"


class TestMainQuestCampaign:
    def test_has_5_act_spine(self):
        data = _load_campaign("main_quest_campaign")
        assert len(data["acts"]) >= 5

    def test_each_act_has_objectives(self):
        data = _load_campaign("main_quest_campaign")
        for act in data["acts"]:
            assert len(act["objectives"]) >= 1, f"{act['id']} has no objectives"

    def test_each_act_has_rewards(self):
        data = _load_campaign("main_quest_campaign")
        for act in data["acts"]:
            assert len(act["rewards"]) >= 1, f"{act['id']} has no rewards"

    def test_objective_ids_unique(self):
        data = _load_campaign("main_quest_campaign")
        all_ids = [o["id"] for act in data["acts"] for o in act["objectives"]]
        assert len(all_ids) == len(set(all_ids)), "Duplicate objective IDs"


# ---------------------------------------------------------------------------
# 4. Quest config
# ---------------------------------------------------------------------------

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
