from pathlib import Path

from engine.api.campaign_runtime import CampaignRuntime
from engine.api.game_engine import GameEngine
from tools.campaign_client import CampaignClient


def test_campaign_client_save_load_round_trip(tmp_path: Path):
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    client = CampaignClient(runtime=runtime)

    created = client.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    save_meta = client.save_campaign(created["campaign_id"], "campaign_client_slot", "Saver")
    loaded = client.load_campaign(str(save_meta["slot_name"]))

    assert loaded["campaign"]["world"]["seed"] == 42
    assert loaded["campaign"]["settlement"]["name"]
    assert loaded["campaign"]["player"]["name"] == "Saver"


def test_campaign_runtime_lists_only_matching_campaign_saves(tmp_path: Path):
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "campaign_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    first = runtime.create_campaign("Saver", "warrior", "fantasy_ember", "standard", 42)
    second = runtime.create_campaign("Saver", "rogue", "scifi_frontier", "standard", 43)
    runtime.save_campaign(first.campaign_id, "first_slot", "Saver")
    runtime.save_campaign(second.campaign_id, "second_slot", "Saver")

    legacy_session = GameEngine(llm=None).new_session("Saver", "warrior", location="Harbor Town")
    runtime.save_system.save_game(legacy_session, "legacy_slot", player_name="Saver")

    listed = runtime.list_campaign_saves(first.campaign_id)

    assert [entry["slot_name"] for entry in listed] == ["first_slot"]
    assert all(entry["campaign_compatible"] for entry in listed)
