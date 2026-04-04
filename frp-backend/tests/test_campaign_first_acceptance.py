from __future__ import annotations

import inspect
from pathlib import Path

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.persistence import campaign_payload
from engine.api.kernel_adapter import start_fight


ACTIVE_RUNTIME_FILES = [
    "engine/api/campaign/runtime.py",
    "engine/api/campaign/runtime_commands.py",
    "engine/api/campaign/context.py",
    "engine/api/campaign_commands.py",
    "engine/api/combat_bridge.py",
    "engine/api/exploration_bridge.py",
    "engine/api/gameplay_bridge.py",
    "engine/api/medical_bridge.py",
]

FORBIDDEN_RUNTIME_TOKENS = [
    '"avatar"',
    "GameEngine",
    "engine.process_action",
    "campaign_state[\"combat_state\"]",
    "NarratorService",
    "DMAIAgent",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runtime() -> CampaignRuntime:
    return CampaignRuntime()


def test_active_campaign_runtime_has_no_legacy_runtime_tokens():
    root = _repo_root()
    for relative_path in ACTIVE_RUNTIME_FILES:
        text = (root / relative_path).read_text(encoding="utf-8")
        for token in FORBIDDEN_RUNTIME_TOKENS:
            assert token not in text, f"Found legacy token {token!r} in {relative_path}"


def test_unknown_command_contract_is_explicit_and_non_avatar():
    runtime = _runtime()
    context = runtime.create_campaign(player_name="GateUnknown", seed=42)

    result = runtime.run_command(context.campaign_id, "sing to the moon")

    assert result["command_type"] == "unknown"
    assert result["hours_advanced"] == 0
    assert "unknown command" in result["narrative"].lower()


def test_campaign_payload_prefers_kernel_combat_state_over_legacy_mirror():
    runtime = _runtime()
    context = runtime.create_campaign(player_name="GateCombat", seed=42)

    actors = (context.kernel_runtime or {}).get("actors", {})
    player = actors["player"]
    target = next(actor for actor_id, actor in actors.items() if actor_id != "player")
    combat = start_fight([player, target], seed=42).to_dict()

    context.kernel_runtime["game_state"].raw_payload["combat"] = combat
    context.campaign_state["combat_state"] = {
        "phase": "legacy_fake",
        "round": 999,
        "combatants": [],
    }

    payload = campaign_payload(context)

    assert payload["scene"] == "combat"
    assert payload["combat"] is not None
    assert payload["combat"]["phase"] == combat["phase"]
    assert payload["combat"]["round"] == combat["round_number"]
    assert payload["combat"]["phase"] != "legacy_fake"


def test_campaign_payload_has_no_top_level_avatar_vocabulary():
    runtime = _runtime()
    context = runtime.create_campaign(player_name="GatePayload", seed=42)

    result = runtime.run_command(context.campaign_id, "rest")

    assert result["command_type"] == "rest"
    assert result["campaign"]["scene"] in {"exploration", "combat", "dialogue", "rest", "transition"}


def test_campaign_runtime_ctor_has_no_llm_parameter():
    signature = inspect.signature(CampaignRuntime)
    assert "llm" not in signature.parameters


def test_campaign_first_surface_has_no_compatibility_facades():
    root = _repo_root()
    assert not (root / "engine/api/campaign_runtime.py").exists()
    assert not (root / "engine/api/campaign_state.py").exists()
    assert not (root / "engine/api/action_parser.py").exists()
