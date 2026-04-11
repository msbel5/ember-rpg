from pathlib import Path

import json
import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel import GameState
from tools.campaign_client import CampaignClient


def test_campaign_client_save_load_round_trip(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    client = CampaignClient(runtime=runtime)

    created = client.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    save_meta = client.save_campaign(created["campaign_id"], "campaign_client_slot", "Saver")
    loaded = client.load_campaign(str(save_meta["slot_name"]))

    assert loaded["campaign"]["world"]["seed"] == 42
    assert loaded["campaign"]["world_state"]["seed"] == 42
    assert loaded["campaign"]["game_state"]["seed"] == 42
    assert loaded["campaign"]["game_state"]["party"] == ["player"]
    assert loaded["campaign"]["actors"]
    assert loaded["campaign"]["jobs"]
    assert loaded["campaign"]["reactions"]
    assert loaded["campaign"]["worksites"]
    assert loaded["campaign"]["colony_pressure"]["food"] >= 0
    assert loaded["campaign"]["path_authority"]["active_region_id"] == loaded["campaign"]["world"]["active_region_id"]
    assert "power_network" in loaded["campaign"]["systems"]
    assert loaded["campaign"]["settlement"]["name"]
    assert loaded["campaign"]["player"]["name"] == "Saver"


def test_campaign_runtime_lists_only_matching_campaign_saves(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    first = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    second = runtime.create_campaign("Saver", "rogue", "scifi_frontier", "standard", 43)
    runtime.save_campaign(first.campaign_id, "first_slot", "Saver")
    runtime.save_campaign(second.campaign_id, "second_slot", "Saver")

    listed = runtime.list_campaign_saves(first.campaign_id)

    assert [entry["slot_name"] for entry in listed] == ["first_slot"]
    assert all(entry["campaign_compatible"] for entry in listed)


def test_campaign_runtime_persists_kernel_game_state_in_campaign_meta():
    runtime = CampaignRuntime()

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    meta = context.campaign_state["campaign"]
    restored = GameState.from_dict(meta["game_state"])

    assert restored.campaign_id == context.campaign_id
    assert restored.seed == 42
    assert restored.current_area_id == meta["active_region_id"]
    assert restored.party == ["player"]


def test_campaign_save_persists_kernel_roots_in_campaign_context(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    runtime.save_campaign(context.campaign_id, "kernel_root_slot", "Saver")
    raw = runtime.save_system.read_save("kernel_root_slot")

    assert raw is not None
    campaign_context = raw["campaign_context"]
    assert "kernel_game_state" not in campaign_context
    assert "kernel_world_state" not in campaign_context
    assert campaign_context["campaign_state"]["campaign"]["game_state"]["campaign_id"] == context.campaign_id
    assert campaign_context["campaign_state"]["campaign"]["world_state"]["seed"] == 42


def test_campaign_load_rejects_invalid_kernel_game_state(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    runtime.save_campaign(context.campaign_id, "broken_kernel_state", "Saver")
    save_data = runtime.save_system.read_save("broken_kernel_state")
    assert save_data is not None
    save_data["campaign_context"]["campaign_state"]["campaign"]["game_state"] = {"seed": 42}
    save_path = runtime.save_system.save_dir / "broken_kernel_state.json"
    save_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")

    with pytest.raises((KeyError, TypeError, ValueError)):
        runtime.load_campaign("broken_kernel_state")


def test_campaign_load_rejects_invalid_kernel_world_state(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    runtime.save_campaign(context.campaign_id, "broken_kernel_world", "Saver")
    save_data = runtime.save_system.read_save("broken_kernel_world")
    assert save_data is not None
    save_data["campaign_context"]["campaign_state"]["campaign"]["world_state"] = {"seed": 42}
    save_path = runtime.save_system.save_dir / "broken_kernel_world.json"
    save_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")

    with pytest.raises((KeyError, TypeError, ValueError)):
        runtime.load_campaign("broken_kernel_world")


def test_campaign_load_rejects_unsupported_save_schema(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    runtime.save_campaign(context.campaign_id, "legacy_schema_slot", "Saver")
    save_data = runtime.save_system.read_save("legacy_schema_slot")
    assert save_data is not None
    save_data["schema_version"] = "3.0"
    save_path = runtime.save_system.save_dir / "legacy_schema_slot.json"
    save_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match=r"schema version|4\.0|3\.0"):
        runtime.load_campaign("legacy_schema_slot")


def test_campaign_player_save_listing_excludes_unsupported_schema(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    context = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    runtime.save_campaign(context.campaign_id, "supported_slot", "Saver")
    runtime.save_campaign(context.campaign_id, "legacy_slot", "Saver")
    legacy_data = runtime.save_system.read_save("legacy_slot")
    assert legacy_data is not None
    legacy_data["schema_version"] = "3.0"
    legacy_path = runtime.save_system.save_dir / "legacy_slot.json"
    legacy_path.write_text(json.dumps(legacy_data, indent=2), encoding="utf-8")

    listed = runtime.list_player_campaign_saves("Saver")

    assert [entry["slot_name"] for entry in listed] == ["supported_slot"]
    assert all(entry["schema_version"] == "4.0" for entry in listed)
