from __future__ import annotations

from engine.kernel.game_state import GameState, normalize_party_state, set_party_formation, swap_party_member


def test_normalize_party_state_deduplicates_party_and_inactive_overlap() -> None:
    state = GameState(
        campaign_id="camp",
        seed=42,
        party=["companion_a", "player", "companion_a", "player"],
        inactive_npcs=["companion_a", "companion_b", "player", "companion_b"],
    )

    normalize_party_state(state)

    assert state.party == ["player", "companion_a"]
    assert state.inactive_npcs == ["companion_b"]


def test_swap_party_member_keeps_party_and_inactive_normalized() -> None:
    state = GameState(
        campaign_id="camp",
        seed=42,
        party=["player", "companion_a", "companion_a"],
        inactive_npcs=["companion_b", "player", "companion_b"],
    )

    success, message = swap_party_member(state, "companion_a", "companion_b")

    assert success is True
    assert message == "swapped"
    assert state.party == ["player", "companion_b"]
    assert state.inactive_npcs == ["companion_a"]


def test_swap_party_member_rejects_invalid_active_inactive_combinations() -> None:
    state = GameState(
        campaign_id="camp",
        seed=42,
        party=["player", "companion_a"],
        inactive_npcs=["companion_b"],
    )

    assert swap_party_member(state, "player", "companion_b") == (False, "invalid swap")
    assert swap_party_member(state, "companion_b", "companion_a") == (False, "invalid swap")
    assert state.party == ["player", "companion_a"]
    assert state.inactive_npcs == ["companion_b"]


def test_set_party_formation_normalizes_supported_values() -> None:
    state = GameState(campaign_id="camp", seed=42, formation="SCATTER")

    success, formation = set_party_formation(state, "line")

    assert success is True
    assert formation == "line"
    assert state.formation == "line"


def test_set_party_formation_rejects_unknown_values() -> None:
    state = GameState(campaign_id="camp", seed=42)

    success, message = set_party_formation(state, "phalanx")

    assert success is False
    assert message == "invalid formation"
    assert state.formation == "wedge"