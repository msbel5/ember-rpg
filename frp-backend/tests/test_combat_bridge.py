"""Tests for the combat bridge: attack/defend/flee command handling.

Verifies STATE CHANGES — HP reduction, wound creation, alive flag,
defensive stance, flee flag — not just narrative strings.
"""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
import engine.api.combat_bridge as combat_bridge
from engine.api.campaign.state_sync import sync_player_position
from engine.api.combat_bridge import build_combat_payload, maybe_handle_combat_command
from engine.kernel import item_stack_from_legacy_payload
from engine.kernel.actor_records import create_monster_actor, create_player_actor
from engine.map import MapData, TileType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    """Create a minimal campaign for testing."""
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="TestPlayer", seed=42)
    return rt, ctx


def _inject_enemy(context, *, base_id="test_goblin", name="Goblin", hp=10, mig=8, agi=8):
    """Inject a test enemy into the kernel runtime actors dict."""
    template = {
        "id": base_id,
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
    player = actors.get("player")
    if player is not None:
        enemy.position.x = int(player.position.x) + 1
        enemy.position.y = int(player.position.y)
    actors[enemy.identity.actor_id] = enemy
    return enemy


def _set_runtime_tick(context, tick: int) -> None:
    context.kernel_runtime["game_state"].world_time.game_tick = int(tick)


def _map_from_rows(*rows: str) -> MapData:
    tile_map = {".": TileType.FLOOR, "#": TileType.WALL}
    tiles = [[tile_map[cell] for cell in row] for row in rows]
    return MapData(
        width=len(rows[0]),
        height=len(rows),
        tiles=tiles,
        rooms=[],
        spawn_point=(0, 0),
    )


# ---------------------------------------------------------------------------
# Attack tests
# ---------------------------------------------------------------------------

class TestAttackCommand:
    def test_attack_duplicate_name_returns_ambiguity(self):
        _rt, ctx = _make_campaign()
        _inject_enemy(ctx, base_id="briga_ward_alpha", name="Briga Ward", hp=20)
        _inject_enemy(ctx, base_id="briga_ward_beta", name="Briga Ward", hp=20)

        result = maybe_handle_combat_command(ctx, "attack Briga Ward")

        assert result is not None
        assert "Multiple actors match 'Briga Ward'" in result[0]

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

    def test_attack_called_shot_passes_zone_from_raw_command(self, monkeypatch: pytest.MonkeyPatch):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        recorded_called_shots: list[str | None] = []
        original_run_attack = combat_bridge.run_attack

        def _recording_run_attack(*args, **kwargs):
            recorded_called_shots.append(kwargs.get("called_shot"))
            return original_run_attack(*args, **kwargs)

        monkeypatch.setattr(combat_bridge, "run_attack", _recording_run_attack)

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name} at head")

        assert result is not None
        assert result[1] == "combat"
        assert "head" in recorded_called_shots

    def test_structured_attack_uses_exact_target_id_and_called_shot(self, monkeypatch: pytest.MonkeyPatch):
        rt, ctx = _make_campaign()
        alpha = _inject_enemy(ctx, base_id="target_alpha", name="Same Name", hp=30)
        _inject_enemy(ctx, base_id="target_beta", name="Same Name", hp=30)
        recorded_called_shots: list[str | None] = []
        original_run_attack = combat_bridge.run_attack

        def _recording_run_attack(*args, **kwargs):
            recorded_called_shots.append(kwargs.get("called_shot"))
            return original_run_attack(*args, **kwargs)

        monkeypatch.setattr(combat_bridge, "run_attack", _recording_run_attack)

        result = rt.run_command(
            ctx.campaign_id,
            "",
            shortcut="combat",
            args={"action_id": "attack", "target_id": alpha.identity.actor_id, "called_shot": "head"},
        )

        assert result["command_type"] == "combat"
        assert "head" in recorded_called_shots

    def test_invalid_called_shot_lists_valid_zones(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=30)

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name} at antenna")

        assert result is not None
        assert result[1] == "combat"
        assert "Invalid called shot 'antenna'" in result[0]
        assert "Valid zones:" in result[0]
        assert "head" in result[0]

    def test_out_of_range_attack_starts_combat_without_free_hit(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=30)
        sync_player_position(ctx, 0, 0, center_viewport=False)
        enemy.position.x = 3
        enemy.position.y = 0
        original_hp = int(enemy.stats["hp"])

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")

        assert result is not None
        assert result[1] == "combat"
        assert "out of range" in result[0].lower()
        assert int(enemy.stats["hp"]) == original_hp
        payload = build_combat_payload(ctx)
        assert payload is not None
        target_entry = next(item for item in payload["targets"] if item["actor_id"] == enemy.identity.actor_id)
        assert target_entry["attackable"] is False
        assert target_entry["attack_blocked_reason"] == "out_of_range"
        assert target_entry["distance"] == 3
        assert target_entry["targeting"]["attack_mode"] == "melee"
        assert target_entry["targeting"]["geometry"] == "contact"

    def test_ranged_attack_requires_clear_line_of_sight(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=30)
        sync_player_position(ctx, 0, 0, center_viewport=False)
        enemy.position.x = 2
        enemy.position.y = 0
        ctx.map_data = _map_from_rows(".#.", "...", "...")
        player = ctx.kernel_runtime["actors"]["player"]
        player.equipment.slots["weapon"] = [
            item_stack_from_legacy_payload(
                {
                    "id": "shortbow",
                    "name": "Shortbow",
                    "slot": "weapon",
                    "attack_profile": {"attack_type": "ranged", "range": 5, "projectile_type": "arrow"},
                }
            )
        ]

        result = maybe_handle_combat_command(ctx, f"attack {enemy.name}")

        assert result is not None
        assert result[1] == "combat"
        assert "line of sight" in result[0].lower()
        payload = build_combat_payload(ctx)
        assert payload is not None
        target_entry = next(item for item in payload["targets"] if item["actor_id"] == enemy.identity.actor_id)
        assert target_entry["attackable"] is False
        assert target_entry["attack_blocked_reason"] == "no_line_of_sight"
        assert target_entry["targeting"]["attack_mode"] == "ranged"
        assert target_entry["targeting"]["geometry"] == "arrow"


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


class TestCombatMovementAndPayload:
    def test_move_updates_position_without_ending_turn(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        start = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert start is not None
        payload = build_combat_payload(ctx)
        assert payload is not None
        option = next((item for item in payload["move_options"] if item["available"]), None)
        assert option is not None, "Expected at least one available move option"
        player = ctx.kernel_runtime["actors"]["player"]
        before_position = (int(player.position.x), int(player.position.y))
        before_movement = next(
            item["turn_resources"]["movement_remaining"]
            for item in payload["combatants"]
            if item["actor_id"] == "player"
        )

        result = maybe_handle_combat_command(ctx, f"move {option['direction']}")

        assert result is not None
        assert result[1] == "combat"
        updated = build_combat_payload(ctx)
        assert updated is not None
        after_position = tuple(
            next(item["position"] for item in updated["combatants"] if item["actor_id"] == "player")
        )
        after_movement = next(
            item["turn_resources"]["movement_remaining"]
            for item in updated["combatants"]
            if item["actor_id"] == "player"
        )
        assert after_position != before_position
        assert updated["turn_actor_id"] == "player"
        assert after_movement == before_movement - 1

    def test_blocked_move_fails_cleanly_and_does_not_change_position(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        sync_player_position(ctx, 0, 0, center_viewport=False)
        ctx.kernel_runtime["actors"][enemy.identity.actor_id].position.x = 2
        ctx.kernel_runtime["actors"][enemy.identity.actor_id].position.y = 0

        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None
        player = ctx.kernel_runtime["actors"]["player"]
        before_position = (int(player.position.x), int(player.position.y))

        result = maybe_handle_combat_command(ctx, "move west")

        assert result is not None
        assert result[1] == "combat"
        assert "edge of the map" in result[0].lower()
        assert (int(player.position.x), int(player.position.y)) == before_position

    def test_wait_alias_routes_to_end_turn(self, monkeypatch: pytest.MonkeyPatch):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None
        monkeypatch.setattr(combat_bridge, "_resolve_non_player_turns", lambda *_args, **_kwargs: [])

        result = maybe_handle_combat_command(ctx, "wait")

        assert result is not None
        assert result[1] == "combat"
        payload = build_combat_payload(ctx)
        assert payload is not None
        assert payload["turn_actor_id"] != "player"

    def test_end_turn_routes_cleanly(self, monkeypatch: pytest.MonkeyPatch):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None
        monkeypatch.setattr(combat_bridge, "_resolve_non_player_turns", lambda *_args, **_kwargs: [])

        result = maybe_handle_combat_command(ctx, "end turn")

        assert result is not None
        assert result[1] == "combat"
        payload = build_combat_payload(ctx)
        assert payload is not None
        assert payload["turn_actor_id"] != "player"

    def test_combat_payload_is_truthful(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None

        payload = build_combat_payload(ctx)

        assert payload is not None
        assert payload["available_actions"] == ["attack", "defend", "flee", "move", "end_turn"]
        assert "move_options" in payload
        assert payload["move_options"]
        player_entry = next(item for item in payload["combatants"] if item["actor_id"] == "player")
        assert len(player_entry["position"]) == 2
        target_entry = next(item for item in payload["targets"] if item["actor_id"] == enemy.identity.actor_id)
        assert "called_shot_zones" in target_entry
        assert "head" in target_entry["called_shot_zones"]

    def test_cast_is_advertised_only_when_player_can_cast(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None

        baseline = build_combat_payload(ctx)
        assert baseline is not None
        assert "cast" not in baseline["available_actions"]

        player = ctx.kernel_runtime["actors"]["player"]
        player.spell_points = 4
        player.raw_payload["max_spell_points"] = 4
        updated = build_combat_payload(ctx)

        assert updated is not None
        assert "cast" in updated["available_actions"]

    def test_cast_works_in_combat_and_ends_turn(self, monkeypatch: pytest.MonkeyPatch):
        rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        player = ctx.kernel_runtime["actors"]["player"]
        player.spell_points = 10
        player.raw_payload["max_spell_points"] = 10
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None
        monkeypatch.setattr(combat_bridge, "_resolve_non_player_turns", lambda *_args, **_kwargs: [])

        cast = rt.run_command(ctx.campaign_id, "cast magic missile")
        use_item = rt.run_command(ctx.campaign_id, "use field tonic")

        assert cast["command_type"] == "spell"
        assert "magic missile" in cast["narrative"].lower()
        assert player.spell_points == 8
        assert cast["campaign"]["combat"]["turn_actor_id"] != "player"
        assert use_item["command_type"] == "combat"
        assert "not available in combat yet" in use_item["narrative"].lower()

    def test_invalid_combat_cast_fails_cleanly_without_ending_turn(self):
        rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=50)
        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None

        cast = rt.run_command(
            ctx.campaign_id,
            "",
            shortcut="spell",
            args={"action_id": "cast", "spell_id": "magic_missile"},
        )

        assert cast["command_type"] == "spell"
        assert "not enough spell points" in cast["narrative"].lower()
        assert cast["campaign"]["combat"]["turn_actor_id"] == "player"

    def test_enemy_turn_moves_closer_when_out_of_range(self):
        _rt, ctx = _make_campaign()
        enemy = _inject_enemy(ctx, hp=30)
        sync_player_position(ctx, 0, 0, center_viewport=False)
        enemy.position.x = 3
        enemy.position.y = 0
        player = ctx.kernel_runtime["actors"]["player"]
        player_hp = int(player.stats["hp"])

        started = maybe_handle_combat_command(ctx, f"attack {enemy.name}")
        assert started is not None
        result = maybe_handle_combat_command(ctx, "end turn")

        assert result is not None
        assert result[1] == "combat"
        assert "advances toward" in result[0].lower()
        assert (int(enemy.position.x), int(enemy.position.y)) == (2, 0)
        assert int(player.stats["hp"]) == player_hp


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
