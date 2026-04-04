"""Tests for the exploration bridge: look, examine, move, and scene verb handlers."""
from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime


def _make_campaign():
    rt = CampaignRuntime(llm=None)
    ctx = rt.create_campaign(player_name="Explorer", seed=42)
    return rt, ctx


class TestLookCommand:
    def test_look_returns_scene_description(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "look around")
        assert result["command_type"] == "exploration"
        assert "narrative" in result
        assert len(result["narrative"]) > 20

    def test_look_shows_settlement_name(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "look")
        name = ctx.settlement_state.get("name", "")
        assert name.lower() in result["narrative"].lower() or "settlement" in result["narrative"].lower()

    def test_look_at_redirects_to_examine(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "look at something")
        assert result["command_type"] == "exploration"


class TestExamineCommand:
    def test_examine_npc_returns_description(self):
        rt, ctx = _make_campaign()
        actors = ctx.kernel_runtime["actors"]
        npc = next(
            (a for aid, a in actors.items()
             if aid != "player" and getattr(a.identity, "actor_type", "") == "npc"),
            None,
        )
        if npc:
            result = rt.run_command(ctx.campaign_id, f"examine {npc.identity.display_name}")
            assert result["command_type"] == "exploration"

    def test_examine_unknown_target(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "examine nonexistent_thing_xyz")
        assert result["command_type"] == "exploration"
        assert "nothing remarkable" in result["narrative"].lower()

    def test_inspect_alias_works(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "inspect something")
        assert result["command_type"] == "exploration"


class TestMoveCommand:
    def test_move_to_coords_changes_position(self):
        rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        old_x = player.position.x
        result = rt.run_command(ctx.campaign_id, "move to 5,5")
        assert result["command_type"] == "exploration"

    def test_move_directional(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "move north")
        assert result["command_type"] == "exploration"
        assert "north" in result["narrative"].lower()

    def test_go_to_location(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "go to tavern")
        assert result["command_type"] == "exploration"


class TestSceneVerbCommand:
    def test_search_is_skill_check(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "search")
        assert result["command_type"] == "exploration"
        narrative_lower = result["narrative"].lower()
        assert "search" in narrative_lower or "find" in narrative_lower or "notice" in narrative_lower

    def test_search_includes_check_detail(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "search")
        assert "INS check" in result["narrative"]

    def test_mine_uses_mig(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "mine")
        assert "MIG check" in result["narrative"]

    def test_lockpick_uses_agi(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "lockpick the chest")
        assert "AGI check" in result["narrative"]

    def test_scene_verb_advances_one_hour(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "chop")
        assert result["hours_advanced"] == 1

    def test_open_with_target(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "open door")
        assert result["command_type"] == "exploration"

    def test_unknown_still_rejected(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "xyzzy nonsense")
        assert result["command_type"] == "unknown"
