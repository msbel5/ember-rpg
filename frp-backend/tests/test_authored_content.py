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
