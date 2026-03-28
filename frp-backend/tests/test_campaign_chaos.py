"""Campaign-stack long-form chaos tests.

Exercises the full CampaignRuntime command loop for hundreds of turns,
mixing avatar and commander commands, saving/loading mid-run, and
asserting that the campaign snapshot stays sane throughout.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from engine.api.campaign_runtime import CampaignRuntime
from tools.campaign_client import CampaignClient


# ---------------------------------------------------------------------------
# Command pools
# ---------------------------------------------------------------------------

AVATAR_COMMANDS = [
    "look around",
    "move north",
    "move south",
    "move east",
    "move west",
    "examine area",
    "inventory",
    "short rest",
    "search",
    "attack",
    "flee",
    "long rest",
]

COMMANDER_COMMANDS_TEMPLATE = [
    "assign {resident} to hauling",
    "assign {resident} to scouting",
    "defend",
    "designate harvest",
    "set stockpile supplies",
    "build workshop",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client(tmp_path: Path, adapter_id: str, profile_id: str = "standard", seed: int = 42) -> CampaignClient:
    """Create a CampaignClient pointing saves at tmp_path."""
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    return CampaignClient(runtime=runtime)


def _assert_snapshot_sane(snapshot: dict, label: str) -> None:
    """Assert minimum viable campaign state."""
    campaign = snapshot.get("campaign", snapshot)
    assert campaign.get("world", {}).get("adapter_id"), f"missing adapter_id at {label}"

    sheet = snapshot.get("character_sheet", {})
    assert sheet.get("name"), f"missing character name at {label}"

    stats = sheet.get("stats", [])
    assert len(stats) == 6, f"expected 6 stats at {label}, got {len(stats)}"

    hp = sheet.get("hp", {})
    assert hp.get("current", -1) >= 0, f"hp below 0 at {label}: {hp}"

    settlement = campaign.get("settlement", {})
    assert settlement.get("name"), f"missing settlement name at {label}"


def _get_resident_name(snapshot: dict) -> str | None:
    """Extract the first resident name from the snapshot, or None."""
    campaign = snapshot.get("campaign", snapshot)
    settlement = campaign.get("settlement", {})
    residents = settlement.get("residents", [])
    if residents:
        return residents[0].get("name")
    return None


def _pick_command(rng: random.Random, snapshot: dict) -> str:
    """Pick a random command from avatar + commander pools."""
    resident_name = _get_resident_name(snapshot)
    pool: list[str] = list(AVATAR_COMMANDS)
    if resident_name:
        for tmpl in COMMANDER_COMMANDS_TEMPLATE:
            pool.append(tmpl.format(resident=resident_name))
    else:
        # If no residents, add only non-resident commander commands
        pool.extend(["defend", "designate harvest", "set stockpile supplies", "build workshop"])
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Deterministic 200-turn pass tests
# ---------------------------------------------------------------------------

_ORDERED_COMMANDS_200 = [
    "look around", "move north", "examine area", "move south",
    "inventory", "talk", "short rest", "move east",
    "attack", "flee", "move west", "search",
    "long rest", "defend", "designate harvest",
    "set stockpile supplies", "build workshop",
]


def _run_200_turn_pass(tmp_path: Path, adapter_id: str) -> None:
    """Core logic for the deterministic 200-turn pass test."""
    client = _build_client(tmp_path, adapter_id)
    snapshot = client.create_campaign("ChaosRunner", "warrior", adapter_id, "standard", seed=42)
    campaign_id = snapshot["campaign_id"]

    _assert_snapshot_sane(snapshot, "turn-0")

    save_slot: str | None = None

    for turn in range(1, 201):
        # Build command for this turn
        idx = turn % len(_ORDERED_COMMANDS_200)
        cmd = _ORDERED_COMMANDS_200[idx]

        # For assign commands, extract a resident name
        if cmd == "talk":
            resident = _get_resident_name(snapshot)
            if resident:
                cmd = f"assign {resident} to scouting"
            else:
                cmd = "look around"

        try:
            snapshot = client.submit_command(campaign_id, cmd)
        except Exception:
            # On error, refresh snapshot and continue
            snapshot = client.get_campaign(campaign_id)

        # Assert every 20 turns
        if turn % 20 == 0:
            _assert_snapshot_sane(snapshot, f"turn-{turn}")

        # Save at turn 100
        if turn == 100:
            meta = client.save_campaign(campaign_id, f"chaos_save_{adapter_id}", "ChaosRunner")
            save_slot = str(meta["slot_name"])

        # Load at turn 150
        if turn == 150 and save_slot:
            loaded = client.load_campaign(save_slot)
            campaign_id = loaded["campaign_id"]
            snapshot = loaded
            _assert_snapshot_sane(snapshot, "post-load-150")

    # Final sanity check
    _assert_snapshot_sane(snapshot, "turn-200-final")


def test_campaign_200_turn_pass_fantasy_ember(tmp_path: Path) -> None:
    _run_200_turn_pass(tmp_path, "fantasy_ember")


def test_campaign_200_turn_pass_scifi_frontier(tmp_path: Path) -> None:
    _run_200_turn_pass(tmp_path, "scifi_frontier")


# ---------------------------------------------------------------------------
# Randomised 500-turn chaos tests
# ---------------------------------------------------------------------------


def _run_500_turn_chaos(tmp_path: Path, adapter_id: str) -> None:
    """Core logic for the randomised 500-turn chaos test."""
    rng = random.Random(42)
    client = _build_client(tmp_path, adapter_id)
    snapshot = client.create_campaign("ChaosAgent", "rogue", adapter_id, "standard", seed=42)
    campaign_id = snapshot["campaign_id"]

    _assert_snapshot_sane(snapshot, "chaos-turn-0")

    save_slot: str | None = None
    error_count = 0

    for turn in range(1, 501):
        cmd = _pick_command(rng, snapshot)

        try:
            snapshot = client.submit_command(campaign_id, cmd)
        except Exception:
            error_count += 1
            try:
                snapshot = client.get_campaign(campaign_id)
            except Exception:
                pass  # campaign may be in an odd state; keep going

        # Assert every 50 turns
        if turn % 50 == 0:
            _assert_snapshot_sane(snapshot, f"chaos-turn-{turn}")

        # Save at turn 250
        if turn == 250:
            try:
                meta = client.save_campaign(campaign_id, f"chaos500_{adapter_id}", "ChaosAgent")
                save_slot = str(meta["slot_name"])
            except Exception:
                error_count += 1

        # Load at turn 350
        if turn == 350 and save_slot:
            try:
                loaded = client.load_campaign(save_slot)
                campaign_id = loaded["campaign_id"]
                snapshot = loaded
                _assert_snapshot_sane(snapshot, "chaos-post-load-350")
            except Exception:
                error_count += 1

    # Final sanity
    _assert_snapshot_sane(snapshot, f"chaos-turn-500-final")

    # Max 5% failure rate = 25 errors out of 500
    max_errors = 25
    assert error_count <= max_errors, (
        f"Too many errors in 500-turn chaos run ({adapter_id}): "
        f"{error_count}/{500} ({error_count * 100 / 500:.1f}%)"
    )


@pytest.mark.slow
def test_campaign_500_turn_chaos_fantasy_ember(tmp_path: Path) -> None:
    _run_500_turn_chaos(tmp_path, "fantasy_ember")


@pytest.mark.slow
def test_campaign_500_turn_chaos_scifi_frontier(tmp_path: Path) -> None:
    _run_500_turn_chaos(tmp_path, "scifi_frontier")
