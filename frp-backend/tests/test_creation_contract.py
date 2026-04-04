"""Tests for the kernel CreationState Q&A + weight accumulation contract.

Verifies that CreationState loads questions from character_creation.json,
accumulates weights from answers, and produces all fields required by
campaign_routes.py and campaign/runtime.py.
"""
from __future__ import annotations

import pytest

from engine.kernel.creation import CreationState, get_creation_catalog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(seed: int = 42) -> CreationState:
    return CreationState(player_name="TestPlayer", rng_seed=seed)


# ---------------------------------------------------------------------------
# Question loading
# ---------------------------------------------------------------------------

class TestQuestionLoading:
    def test_questions_loaded_from_json(self):
        state = _make_state()
        assert len(state.question_groups) > 0, "Should load question groups"

    def test_each_group_has_questions(self):
        state = _make_state()
        for group in state.question_groups:
            assert "id" in group
            assert "questions" in group
            assert len(group["questions"]) > 0

    def test_each_question_has_answers(self):
        state = _make_state()
        for group in state.question_groups:
            for question in group["questions"]:
                assert "id" in question
                assert "answers" in question
                assert len(question["answers"]) >= 2

    def test_questions_property_flattened(self):
        state = _make_state()
        assert len(state.questions) > 0
        for q in state.questions:
            assert "id" in q
            assert "answers" in q


# ---------------------------------------------------------------------------
# Weight accumulation
# ---------------------------------------------------------------------------

class TestWeightAccumulation:
    def test_initial_weights_are_empty(self):
        state = _make_state()
        assert state.class_weights == {}
        assert state.skill_weights == {}
        assert state.alignment_axes == {"law_chaos": 0, "good_evil": 0}
        assert state.facet_scores == {}
        assert state.adapter_bias == {}
        assert state.faction_bias == {}
        assert state.settlement_bias == {}

    def test_answer_question_accumulates_class_weights(self):
        state = _make_state()
        q = state.questions[0]
        a = q["answers"][0]
        state.answer_question(q["id"], a["id"])
        assert len(state.class_weights) > 0, "Should accumulate class weights"

    def test_answer_question_accumulates_alignment(self):
        state = _make_state()
        q = state.questions[0]
        a = q["answers"][0]
        expected_law = a.get("alignment_axes", {}).get("law_chaos", 0)
        expected_good = a.get("alignment_axes", {}).get("good_evil", 0)
        state.answer_question(q["id"], a["id"])
        assert state.alignment_axes["law_chaos"] == expected_law
        assert state.alignment_axes["good_evil"] == expected_good

    def test_multiple_answers_stack(self):
        state = _make_state()
        for q in state.questions[:2]:
            a = q["answers"][0]
            state.answer_question(q["id"], a["id"])
        assert len(state.answers) == 2

    def test_answer_records_history(self):
        state = _make_state()
        q = state.questions[0]
        a = q["answers"][0]
        state.answer_question(q["id"], a["id"])
        assert len(state.answers) == 1
        assert state.answers[0]["question_id"] == q["id"]
        assert state.answers[0]["answer_id"] == a["id"]

    def test_invalid_question_raises(self):
        state = _make_state()
        with pytest.raises(ValueError, match="Unknown question"):
            state.answer_question("nonexistent_q", "some_a")

    def test_invalid_answer_raises(self):
        state = _make_state()
        q = state.questions[0]
        with pytest.raises(ValueError, match="Unknown answer"):
            state.answer_question(q["id"], "nonexistent_a")


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def _answer_all_warrior(self, state: CreationState) -> None:
        """Answer all questions with the most warrior-biased answer."""
        for q in state.questions:
            best = max(q["answers"], key=lambda a: a.get("class_weights", {}).get("warrior", 0))
            state.answer_question(q["id"], best["id"])

    def test_recommended_class(self):
        state = _make_state()
        self._answer_all_warrior(state)
        assert state.recommended_class() == "warrior"

    def test_recommended_class_empty_weights_returns_default(self):
        state = _make_state()
        result = state.recommended_class()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_recommended_alignment(self):
        state = _make_state()
        self._answer_all_warrior(state)
        alignment = state.recommended_alignment()
        assert isinstance(alignment, str)
        assert len(alignment) in (2, 3)  # e.g. "LG", "TN"

    def test_recommended_skills(self):
        state = _make_state()
        self._answer_all_warrior(state)
        skills = state.recommended_skills("warrior")
        assert isinstance(skills, list)
        assert len(skills) > 0


# ---------------------------------------------------------------------------
# Genesis and hints
# ---------------------------------------------------------------------------

class TestGenesisAndHints:
    def test_campaign_genesis(self):
        state = _make_state()
        q = state.questions[0]
        state.answer_question(q["id"], q["answers"][0]["id"])
        genesis = state.campaign_genesis()
        assert "settlement_bias" in genesis
        assert "faction_bias" in genesis
        assert genesis["world_premise"]
        assert genesis["history_events"]
        assert genesis["history_timeline"]

    def test_world_seed_hints(self):
        state = _make_state()
        q = state.questions[0]
        state.answer_question(q["id"], q["answers"][0]["id"])
        hints = state.world_seed_hints()
        assert isinstance(hints, dict)
        assert hints["preferred_adapter"]

    def test_allocation_rules(self):
        state = _make_state()
        rules = state.allocation_rules()
        assert "mode" in rules
        assert "abilities" in rules


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_has_all_required_fields(self):
        state = _make_state()
        state.ensure_roll()
        q = state.questions[0]
        state.answer_question(q["id"], q["answers"][0]["id"])
        d = state.to_dict()
        required = [
            "creation_id", "question_groups", "questions", "answers",
            "class_weights", "skill_weights", "alignment_axes",
            "facet_scores", "adapter_bias", "faction_bias", "settlement_bias",
            "campaign_genesis", "world_seed_hints", "allocation_rules",
            "recommended_class", "recommended_alignment", "recommended_skills",
            "current_roll", "saved_roll", "roll_pool", "saved_roll_pool",
        ]
        for field in required:
            assert field in d, f"Missing field: {field}"

    def test_to_dict_roll_pool_matches_current_roll(self):
        state = _make_state()
        state.ensure_roll()
        d = state.to_dict()
        assert d["roll_pool"] == sorted(d["current_roll"], reverse=True)
        assert d["saved_roll_pool"] == []


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_answers_same_weights(self):
        s1 = _make_state(seed=99)
        s2 = _make_state(seed=99)
        for q in s1.questions:
            s1.answer_question(q["id"], q["answers"][0]["id"])
            s2.answer_question(q["id"], q["answers"][0]["id"])
        assert s1.class_weights == s2.class_weights
        assert s1.alignment_axes == s2.alignment_axes

    def test_different_answers_different_weights(self):
        s1 = _make_state(seed=99)
        s2 = _make_state(seed=99)
        q = s1.questions[0]
        s1.answer_question(q["id"], q["answers"][0]["id"])
        s2.answer_question(q["id"], q["answers"][-1]["id"])
        assert s1.class_weights != s2.class_weights


# ---------------------------------------------------------------------------
# Integration with CampaignRuntime
# ---------------------------------------------------------------------------

class TestCampaignRuntimeIntegration:
    def test_start_creation_returns_valid_context(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime(llm=None)
        ctx = rt.start_creation(player_name="Tester", seed=42)
        assert ctx.state.creation_id
        assert len(ctx.state.question_groups) > 0

    def test_answer_creation_updates_weights(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime(llm=None)
        ctx = rt.start_creation(player_name="Tester", seed=42)
        q = ctx.state.questions[0]
        ctx = rt.answer_creation(ctx.state.creation_id, q["id"], q["answers"][0]["id"])
        assert len(ctx.state.class_weights) > 0

    def test_finalize_creation_produces_campaign(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime(llm=None)
        ctx = rt.start_creation(player_name="Tester", seed=42)
        for q in ctx.state.questions:
            rt.answer_creation(ctx.state.creation_id, q["id"], q["answers"][0]["id"])
        campaign = rt.finalize_creation(ctx.state.creation_id)
        assert campaign.campaign_id
        assert campaign.player is not None
