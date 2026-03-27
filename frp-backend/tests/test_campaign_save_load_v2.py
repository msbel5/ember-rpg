from pathlib import Path

from engine.api.campaign_runtime import CampaignRuntime
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
