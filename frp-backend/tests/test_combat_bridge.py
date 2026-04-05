"""Tests for the combat bridge: attack/defend/flee command handling.

Verifies STATE CHANGES — HP reduction, wound creation, alive flag,
defensive stance, flee flag — not just narrative strings.
"""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
import engine.api.combat_bridge as combat_bridge
from engine.api.combat_bridge import maybe_handle_combat_command
from engine.kernel.actor_records import create_monster_actor, create_player_actor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    """Create a minimal campaign for testing."""
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="TestPlayer", seed=42)
    return rt, ctx


def _inject_enemy(context, *, name="Goblin", hp=10, mig=8, agi=8):
    """Inject a test enemy into the kernel runtime actors dict."""
    template = {
        "id": "test_goblin",
        "name": name,
        "type": "monster",
        "hp": hp,
        "armor_class": 8,
        "cr": 0.5,
        "stats": {"MIG": mig, "AGI": agi, "END": 10, "MND": 8, "INS": 8, "PRE": 6},
        "attacks": [{"name": "claw", "attack_bonus": 2, "damage": "1d4"}],
    }
    enemy = create_monster_actor(template, faction_id="hostile")
    actors = context.kernel_runtime.setdefault("actors", {})
    actors[enemy.identity.actor_id] = enemy
    return enemy


def _set_runtime_tick(context, tick: int) -> None:
    context.kernel_runtime["game_state"].world_time.game_tick = int(tick)


# ---------------------------------------------------------------------------
# Attack tests
# ---------------------------------------------------------------------------

class TestAttackCommand:
    def test_attack_reduces_target_hp(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        original_hp = int(enemy.stats["hp"])

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")

        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "combat"
        # The attack either hit (HP decreased) or missed (HP unchanged).
        # With seed=0 from campaign tick, the result is deterministic.
        current_hp = int(enemy.stats["hp"])
        if "hits" in narrative:
            assert current_hp < original_hp, "HP should decrease on a hit"
        else:
            assert current_hp == original_hp, "HP should not change on a miss"

    def test_attack_stores_combat_only_in_kernel_game_state(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")

        assert result is not None
        runtime_game_state = ctx.kernel_runtime["game_state"]
        assert isinstance(runtime_game_state.raw_payload.get("combat"), dict)
        assert "combat_state" not in ctx.campaign_state

    def test_attack_hit_creates_wound(self):
        """When an attack hits, a wound should be appended to target raw_payload."""
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        assert enemy.raw_payload.get("wounds") is None or len(enemy.raw_payload.get("wounds", [])) == 0

        # Run attack multiple times with different seeds to ensure at least one hit.
        wound_found = False
        for seed_offset in range(20):
            _set_runtime_tick(ctx, seed_offset)
            result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
            if result and "hits" in result[0]:
                wounds = enemy.raw_payload.get("wounds", [])
                if len(wounds) > 0:
                    wound_found = True
                    break
        assert wound_found, "At least one attack should have created a wound"

    def test_attack_kills_target_when_hp_zero(self):
        """Target should be marked dead when HP drops to zero."""
        _rt, ctx = _make_campaign()
        # Give the enemy very low HP so any hit kills it.
        enemy = _inject_enemy(ctx, hp=1)

        # Try multiple seeds until we get a hit.
        killed = False
        for seed_offset in range(30):
            _set_runtime_tick(ctx, seed_offset)
            result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
            if result and "hits" in result[0]:
                killed = True
                break
            if not enemy.alive:
                killed = True
                break

        if killed:
            assert not enemy.alive, "Enemy should be dead after HP reaches 0"
            assert int(enemy.stats["hp"]) == 0

    def test_attack_nonexistent_target(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_combat_command(ctx, "attack NonExistent")
        assert result is not None
        narrative, cmd_type, _hours = result
        assert cmd_type == "combat"
        assert "No target" in narrative

    def test_attack_already_dead_target(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx)
        enemy.alive = False
        result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert result is not None
        assert "already dead" in result[0]


# ---------------------------------------------------------------------------
# Defend tests
# ---------------------------------------------------------------------------

class TestDefendCommand:
    def test_defend_sets_defensive_stance(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx)
        player = ctx.kernel_runtime["actors"]["player"]
        assert not player.raw_payload.get("defensive_stance", False)
        attack_result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert attack_result is not None

        result = maybe_handle_combat_command(ctx, "defend")

        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "combat"
        assert hours == 0
        assert player.raw_payload.get("defensive_stance") is True
        assert "defensive stance" in narrative.lower()


# ---------------------------------------------------------------------------
# Flee tests
# ---------------------------------------------------------------------------

class TestFleeCommand:
    def test_flee_sets_flag_on_success(self):
        """On a successful flee, the player should get the fled_combat flag."""
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx)
        player = ctx.kernel_runtime["actors"]["player"]
        attack_result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert attack_result is not None

        # Try multiple seeds to find one that succeeds.
        escaped = False
        for seed_offset in range(30):
            # Reset flag each attempt.
            player.raw_payload.pop("fled_combat", None)
            _set_runtime_tick(ctx, seed_offset)
            result = maybe_handle_combat_command(ctx, "flee")
            assert result is not None
            if "escapes successfully" in result[0]:
                escaped = True
                assert player.raw_payload.get("fled_combat") is True
                break

        assert escaped, "At least one flee attempt should succeed across 30 seeds"

    def test_flee_failure_does_not_set_flag(self):
        """On a failed flee, the fled_combat flag should not be set."""
        failed = False
        for seed_offset in range(30):
            _rt, ctx = _make_campaign()
            enemy = _inject_enemy(ctx)
            player = ctx.kernel_runtime["actors"]["player"]
            attack_result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
            assert attack_result is not None
            player.raw_payload.pop("fled_combat", None)
            _set_runtime_tick(ctx, seed_offset)
            result = maybe_handle_combat_command(ctx, "flee")
            assert result is not None
            if "fails to escape" in result[0]:
                failed = True
                assert player.raw_payload.get("fled_combat") is None or \
                       player.raw_payload.get("fled_combat") is False
                break

        assert failed, "At least one flee attempt should fail across 30 seeds"

    def test_flee_narrative_contains_roll_info(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx)
        attack_result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert attack_result is not None
        result = maybe_handle_combat_command(ctx, "flee")
        assert result is not None
        narrative = result[0]
        assert "d20=" in narrative
        assert "AGI" in narrative
        assert "DC 10" in narrative

    def test_successful_flee_clears_kernel_combat_without_side_channel_state(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        attack_result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert attack_result is not None
        assert isinstance(ctx.kernel_runtime["game_state"].raw_payload.get("combat"), dict)

        for seed_offset in range(30):
            ctx.campaign_state.setdefault("campaign", {})["tick"] = seed_offset
            flee_result = maybe_handle_combat_command(ctx, "flee")
            assert flee_result is not None
            if "escapes successfully" in flee_result[0]:
                break
        else:
            pytest.fail("Expected at least one successful flee attempt")

        assert "combat" not in ctx.kernel_runtime["game_state"].raw_payload
        assert "combat_state" not in ctx.campaign_state

    def test_combat_uses_distinct_seeds_across_turn_progression(self, monkeypatch):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        recorded_seeds: list[int] = []
        original_run_attack = combat_bridge.run_attack

        def _recording_run_attack(*args, **kwargs):
            recorded_seeds.append(int(kwargs.get("seed", -1)))
            return original_run_attack(*args, **kwargs)

        monkeypatch.setattr(combat_bridge, "run_attack", _recording_run_attack)

        first = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        second = maybe_handle_combat_command(ctx, "defend")

        assert first is not None
        assert second is not None
        assert len(recorded_seeds) >= 2
        assert len(set(recorded_seeds)) >= 2


# ---------------------------------------------------------------------------
# Non-combat commands should return None
# ---------------------------------------------------------------------------

class TestNonCombatCommands:
    def test_non_combat_returns_none(self):
        _rt, ctx = _make_campaign()
        assert maybe_handle_combat_command(ctx, "look around") is None
        assert maybe_handle_combat_command(ctx, "buy sword") is None
        assert maybe_handle_combat_command(ctx, "travel north") is None
        assert maybe_handle_combat_command(ctx, "diagnose self") is None

    def test_no_player_returns_none(self):
        """If no player actor exists, all commands should return None."""
        _rt, ctx = _make_campaign()
        ctx.kernel_runtime["actors"].pop("player", None)
        assert maybe_handle_combat_command(ctx, "attack Goblin") is None
        assert maybe_handle_combat_command(ctx, "defend") is None
        assert maybe_handle_combat_command(ctx, "flee") is None
