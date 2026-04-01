from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.area import AreaState
from engine.kernel.game_state import (
    FORMATIONS,
    DifficultySettings,
    GameState,
    JournalEntry,
    WorldTime,
    add_journal_entry,
    add_to_party,
    advance_time,
    create_game_state,
    derive_seed,
    get_global_variable,
    get_latest_stage,
    modify_reputation,
    remove_from_party,
    set_global_variable,
    transition_to_area,
)


def _actor(actor_id: str) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="pc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
    )


def test_ac01_add_to_party_fails_when_party_is_full():
    state = create_game_state("camp", 42)
    state.party = [f"pc_{index}" for index in range(6)]

    success, message = add_to_party(state, "pc_6")

    assert success is False
    assert message == "party full"


def test_ac02_add_to_party_succeeds_when_party_has_space():
    state = create_game_state("camp", 42)
    state.party = [f"pc_{index}" for index in range(5)]

    success, _message = add_to_party(state, "pc_5")

    assert success is True
    assert len(state.party) == 6


def test_ac03_transition_to_area_evicts_oldest_when_cache_exceeds_limit():
    state = create_game_state("camp", 42)
    state.loaded_area_ids = ["a1", "a2", "a3", "a4"]
    state.loaded_areas = {area_id: AreaState(area_id=area_id) for area_id in state.loaded_area_ids}
    state.raw_payload["max_area_cache"] = 4

    result = transition_to_area(state, "a5")

    assert result["evicted"] == "a1"
    assert state.loaded_area_ids == ["a2", "a3", "a4", "a5"]


def test_ac04_global_variable_round_trip_in_global_scope():
    state = create_game_state("camp", 42)

    set_global_variable(state, "GLOBAL", "quest_1_done", True)

    assert get_global_variable(state, "GLOBAL", "quest_1_done") is True


def test_ac05_add_journal_entry_updates_latest_stage():
    state = create_game_state("camp", 42)

    add_journal_entry(state, "Reached stage 3", quest_id="main_quest", quest_stage=3)

    assert get_latest_stage(state, "main_quest") == 3


def test_ac06_advance_time_updates_tick_and_hour():
    state = create_game_state("camp", 42)

    advance_time(state, 250)

    assert state.world_time.game_tick == 250
    assert state.world_time.hour == 14


def test_ac07_modify_reputation_clamps_to_one():
    state = create_game_state("camp", 42)
    state.reputation = 10

    assert modify_reputation(state, -12) == 1


def test_ac08_difficulty_from_level_hard_uses_expected_multipliers():
    difficulty = DifficultySettings.from_level("hard")

    assert difficulty.enemy_damage_mult == 1.5
    assert difficulty.party_damage_mult == 0.75


def test_ac09_derive_seed_is_stable_for_same_inputs():
    assert derive_seed(42, "combat") == derive_seed(42, "combat")


def test_ac10_game_state_round_trip_preserves_all_fields():
    state = GameState(
        campaign_id="camp",
        seed=42,
        party=["pc_1"],
        inactive_npcs=["npc_1"],
        current_area_id="area_1",
        loaded_area_ids=["area_1"],
        loaded_areas={"area_1": AreaState(area_id="area_1", current_hour=18)},
        actors={"pc_1": _actor("pc_1")},
        global_variables={"quest_done": True},
        local_variables={"area_1": {"lever": "pulled"}},
        journal=[JournalEntry(entry_id="j1", text="Started", quest_id="main", quest_stage=1, timestamp=50, entry_type="quest")],
        world_time=WorldTime(game_tick=250, hour=14, day=1, weather="rain"),
        reputation=12,
        difficulty=DifficultySettings.from_level("core"),
        formation="wedge",
        play_time_ticks=250,
        creation_date="2026-04-01",
        raw_payload={"max_area_cache": 4},
    )

    restored = GameState.from_dict(state.to_dict())

    assert restored == state


def test_remove_from_party_moves_member_to_inactive_pool():
    state = create_game_state("camp", 42)
    state.party = ["pc_1", "pc_2"]

    remove_from_party(state, "pc_2")

    assert state.party == ["pc_1"]
    assert state.inactive_npcs == ["pc_2"]


def test_formations_include_wedge_offsets_for_six_slots():
    assert len(FORMATIONS["wedge"]) == 6
