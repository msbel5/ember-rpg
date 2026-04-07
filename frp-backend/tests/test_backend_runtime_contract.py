"""Backend runtime command contract guard rails.

These tests protect the campaign runtime dispatch contract while the
kernel-direct cutover is in progress. They intentionally verify routing,
not detailed gameplay semantics, so that deleted wrappers or accidental
fallbacks are caught quickly.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign import runtime_commands


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="ContractTester", seed=42)
    return runtime, context


def _unexpected_fallback(*_args, **_kwargs):
    raise AssertionError("legacy avatar fallback should not be called")


def _stub_runtime_shell(monkeypatch: pytest.MonkeyPatch, runtime: CampaignRuntime) -> None:
    monkeypatch.setattr(runtime_commands, "_advance_world", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_commands, "campaign_payload", lambda context: {"campaign_id": context.campaign_id})
    monkeypatch.setattr(runtime_commands, "snapshot_hash", lambda _payload: "contract-hash")
    monkeypatch.setattr(runtime_commands, "trace_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runtime_commands,
        "build_dialog_payload",
        lambda _context, narrative: {"dialog_text": narrative, "dialog_options": []},
    )


def _clear_top_level_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_commands, "maybe_handle_commander_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_commands, "maybe_handle_dialog_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_commands, "maybe_handle_commerce_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_commands, "maybe_handle_medical_command", lambda *_args, **_kwargs: None)


def _handler_stub(command: str, command_type: str) -> Callable:
    def _inner(_context, issued: str):
        if issued == command:
            return (f"handled {command_type}", command_type, 0)
        return None

    return _inner


@pytest.mark.parametrize(
    ("command", "command_type", "module_name", "attr_name", "patch_runtime"),
    [
        ("equip iron_shortsword", "equipment", "engine.api.gameplay_bridge", "maybe_handle_equipment_command", False),
        ("pickup iron_ore", "inventory", "engine.api.gameplay_bridge", "maybe_handle_inventory_command", False),
        ("craft iron_bar", "craft", "engine.api.gameplay_bridge", "maybe_handle_craft_command", False),
        ("rest", "rest", "engine.api.gameplay_bridge", "maybe_handle_rest_command", False),
        ("cast magic missile", "spell", "engine.api.gameplay_bridge", "maybe_handle_spell_command", False),
        ("accept supply_run", "quest", "engine.api.campaign.runtime_commands", "maybe_handle_quest_command", True),
        ("quests", "quest", "engine.api.campaign.runtime_commands", "maybe_handle_quest_command", True),
        ("report supply_run", "quest", "engine.api.campaign.runtime_commands", "maybe_handle_quest_command", True),
        ("buy rope", "commerce", "engine.api.campaign.runtime_commands", "maybe_handle_commerce_command", True),
        ("sell rope", "commerce", "engine.api.campaign.runtime_commands", "maybe_handle_commerce_command", True),
        ("rent room", "commerce", "engine.api.campaign.runtime_commands", "maybe_handle_commerce_command", True),
        ("identify strange ring", "commerce", "engine.api.campaign.runtime_commands", "maybe_handle_commerce_command", True),
        ("diagnose self", "medical", "engine.api.campaign.runtime_commands", "maybe_handle_medical_command", True),
        ("dialog greet", "dialog", "engine.api.campaign.runtime_commands", "maybe_handle_dialog_command", True),
    ],
)
def test_runtime_routes_specialized_commands_without_avatar_fallback(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    command_type: str,
    module_name: str,
    attr_name: str,
    patch_runtime: bool,
):
    runtime, context = _make_campaign()
    _stub_runtime_shell(monkeypatch, runtime)
    _clear_top_level_handlers(monkeypatch)

    module = runtime_commands if patch_runtime else import_module(module_name)
    monkeypatch.setattr(module, attr_name, _handler_stub(command, command_type))

    result = runtime.run_command(context.campaign_id, command)

    assert result["command_type"] == command_type
    assert result["narrative"] == f"handled {command_type}"
    assert result["campaign"]["campaign_id"] == context.campaign_id


def test_runtime_routes_attack_through_combat_bridge(monkeypatch: pytest.MonkeyPatch):
    runtime, context = _make_campaign()
    _stub_runtime_shell(monkeypatch, runtime)
    _clear_top_level_handlers(monkeypatch)

    from engine.api import combat_bridge
    monkeypatch.setattr(
        combat_bridge,
        "maybe_handle_combat_command",
        lambda _context, issued: ("handled combat", "combat", 0) if "attack" in issued else None,
    )

    result = runtime.run_command(context.campaign_id, "attack goblin")

    assert result["command_type"] == "combat"
    assert result["narrative"] == "handled combat"
    assert result["campaign"]["campaign_id"] == context.campaign_id


def test_runtime_rejects_unknown_commands_without_scene_fallback(monkeypatch: pytest.MonkeyPatch):
    runtime, context = _make_campaign()
    _stub_runtime_shell(monkeypatch, runtime)
    _clear_top_level_handlers(monkeypatch)

    result = runtime.run_command(context.campaign_id, "sing to the moon")

    assert result["command_type"] == "unknown"
    assert "unknown command" in result["narrative"].lower()


def test_runtime_rest_smoke_uses_specialized_handler():
    runtime, context = _make_campaign()

    result = runtime.run_command(context.campaign_id, "rest")

    assert result["command_type"] == "rest"
    assert result["campaign_id"] == context.campaign_id
    assert result["hours_advanced"] == 1
    assert "short rest" in result["narrative"].lower()
    assert isinstance(result["campaign"], dict)
    assert "player" in result["campaign"]
