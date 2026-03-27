from pathlib import Path

from engine.api.campaign_runtime import CampaignRuntime
from tools.campaign_client import CampaignClient
from tools.play_topdown import MapState, render_map


def test_terminal_campaign_loop_smoke(tmp_path: Path):
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "terminal_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    client = CampaignClient(runtime=runtime)

    snapshot = client.create_campaign("TerminalProbe", "rogue", "scifi_frontier", "standard", 77)
    map_state = MapState(snapshot)
    panel = render_map(map_state)

    response = client.submit_command(snapshot["campaign_id"], "assign Scout to hauling")
    save_meta = client.save_campaign(snapshot["campaign_id"], "terminal_probe", "TerminalProbe")
    loaded = client.load_campaign(str(save_meta["slot_name"]))

    assert panel is not None
    assert map_state.width == 80 and map_state.height == 60
    assert response["campaign"]["settlement"]["jobs"]
    assert loaded["campaign"]["world"]["adapter_id"] == "scifi_frontier"
