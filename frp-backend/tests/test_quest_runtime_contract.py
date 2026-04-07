"""
Quest runtime release gate.

Freezes the public quest command contract: accept, quests/journal, report.
Covers deterministic setup, save/load preservation, and idempotent reporting.
"""

from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.gameplay import spawn_ground_item_entity


# ── Helpers ──────────────────────────────────────────────────────────


def _make_campaign(seed: int = 42) -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign("QuestGate", "warrior", "fantasy_ember", "standard", seed)
    return runtime, context


def _inject_quest_offer(context, quest_id: str = "test_quest", title: str = "Test Quest") -> None:
    offer = {
        "id": quest_id,
        "quest_id": quest_id,
        "title": title,
        "reward_gold": 50,
        "reward_xp": 100,
        "objectives": [
            {"type": "visit", "region_id": context.region_snapshot.region_id, "required": 1},
        ],
    }
    context.quest_offers = [offer]
    context.campaign_state["quest_offers"] = [offer]


# ═════════════════════════════════════════════════════════════════════
#  Accept quest
# ═════════════════════════════════════════════════════════════════════


class TestAcceptQuest:
    def test_accept_returns_quest_command_type(self):
        runtime, context = _make_campaign()
        _inject_quest_offer(context)
        result = runtime.run_command(context.campaign_id, "accept test_quest")
        assert result["command_type"] == "quest"

    def test_accept_creates_active_quest(self):
        runtime, context = _make_campaign(seed=43)
        _inject_quest_offer(context)
        runtime.run_command(context.campaign_id, "accept test_quest")
        active = context.campaign_state.get("active_quests", [])
        assert any(q["quest_id"] == "test_quest" for q in active)

    def test_accept_nonexistent_quest_still_returns_quest_type(self):
        runtime, context = _make_campaign(seed=44)
        result = runtime.run_command(context.campaign_id, "accept nonexistent_quest_xyz")
        assert result["command_type"] == "quest"


# ═════════════════════════════════════════════════════════════════════
#  Quests / journal
# ═════════════════════════════════════════════════════════════════════


class TestQuestsJournal:
    def test_quests_command_returns_quest_type(self):
        runtime, context = _make_campaign(seed=45)
        result = runtime.run_command(context.campaign_id, "quests")
        assert result["command_type"] == "quest"

    def test_quests_lists_active_quest_after_accept(self):
        runtime, context = _make_campaign(seed=46)
        _inject_quest_offer(context, quest_id="journal_test", title="Journal Test")
        runtime.run_command(context.campaign_id, "accept journal_test")
        result = runtime.run_command(context.campaign_id, "quests")
        assert result["command_type"] == "quest"
        assert "journal_test" in result["narrative"].lower() or "Journal Test" in result["narrative"]

    def test_journal_alias_returns_active_quest_state(self):
        runtime, context = _make_campaign(seed=460)
        _inject_quest_offer(context, quest_id="journal_alias", title="Journal Alias")
        runtime.run_command(context.campaign_id, "accept journal_alias")
        result = runtime.run_command(context.campaign_id, "journal")
        assert result["command_type"] == "quest"
        assert "journal_alias" in result["narrative"].lower() or "Journal Alias" in result["narrative"]


# ═════════════════════════════════════════════════════════════════════
#  Report quest — idempotent, rewards once
# ═════════════════════════════════════════════════════════════════════


class TestReportQuest:
    def test_report_returns_quest_type(self):
        runtime, context = _make_campaign(seed=47)
        _inject_quest_offer(context)
        from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives
        start_quest(context, "test_quest")
        sync_runtime_objectives(context)
        result = runtime.run_command(context.campaign_id, "report test_quest")
        assert result["command_type"] == "quest"

    def test_report_completes_quest_and_marks_completed(self):
        runtime, context = _make_campaign(seed=48)
        _inject_quest_offer(context, quest_id="complete_test")
        from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives
        start_quest(context, "complete_test")
        sync_runtime_objectives(context)
        runtime.run_command(context.campaign_id, "report complete_test")
        assert "complete_test" in context.campaign_state.get("completed_quest_ids", [])

    def test_report_twice_does_not_double_reward(self):
        runtime, context = _make_campaign(seed=49)
        _inject_quest_offer(context, quest_id="reward_test")
        from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives
        start_quest(context, "reward_test")
        sync_runtime_objectives(context)
        player = context.kernel_runtime["actors"]["player"]
        gold_before = int(player.raw_payload.get("gold", player.stats.get("gold", 0)))
        first = runtime.run_command(context.campaign_id, "report reward_test")
        second = runtime.run_command(context.campaign_id, "report reward_test")
        gold_after = int(player.raw_payload.get("gold", player.stats.get("gold", 0)))
        assert "already" in second["narrative"].lower()
        # Gold should have increased exactly once
        assert gold_after == gold_before + 50


# ═════════════════════════════════════════════════════════════════════
#  Save/load preserves quest state
# ═════════════════════════════════════════════════════════════════════


class TestQuestSaveLoad:
    def test_active_quest_survives_save_load(self):
        runtime, context = _make_campaign(seed=50)
        _inject_quest_offer(context, quest_id="persist_test")
        from engine.api.campaign.quest_bridge import start_quest
        start_quest(context, "persist_test")
        runtime.save_campaign(context.campaign_id, "quest_gate_slot", "QuestGate")
        loaded = runtime.load_campaign("quest_gate_slot")
        active = loaded.campaign_state.get("active_quests", [])
        assert any(q["quest_id"] == "persist_test" for q in active)

    def test_completed_quest_survives_save_load(self):
        runtime, context = _make_campaign(seed=51)
        _inject_quest_offer(context, quest_id="complete_persist")
        from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives
        start_quest(context, "complete_persist")
        sync_runtime_objectives(context)
        runtime.run_command(context.campaign_id, "report complete_persist")
        runtime.save_campaign(context.campaign_id, "quest_complete_slot", "QuestGate")
        loaded = runtime.load_campaign("quest_complete_slot")
        assert "complete_persist" in loaded.campaign_state.get("completed_quest_ids", [])
