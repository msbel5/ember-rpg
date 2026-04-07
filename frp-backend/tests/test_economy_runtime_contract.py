"""
Economy runtime release gate.

Freezes the public commerce command contract: buy, sell, rent room, identify.
Covers command_type routing, inventory/gold mutation, and service dispatch.
"""

from __future__ import annotations

import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

import pytest

import engine.api.campaign.runtime_commands as runtime_commands
from engine.api.campaign import commerce_commands
from engine.kernel.store import sell_item
from _release_gate_helpers import (  # noqa: E402
    inventory_quantity,
    make_runtime_campaign,
    seed_live_store_item,
    seed_player_gold,
)


@pytest.fixture(autouse=True)
def _no_world_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    real_advance_world = runtime_commands._advance_world

    def _wrapped_advance_world(context, command_type, hours_advanced, command_text):
        if command_type == "commerce":
            return []
        return real_advance_world(context, command_type, hours_advanced, command_text)

    monkeypatch.setattr(runtime_commands, "_advance_world", _wrapped_advance_world)


def _commerce_command(runtime, context, command: str) -> dict:
    result = runtime.run_command(context.campaign_id, command)
    assert result["campaign_id"] == context.campaign_id
    return result


def _player_gold(context) -> int:
    player = context.kernel_runtime["actors"]["player"]
    return int(player.stats.get("gold", player.raw_payload.get("gold", 0)) or 0)


def _setup_campaign(seed: int) -> tuple[object, object]:
    runtime, context = make_runtime_campaign(player_name="EconGate", seed=seed)
    seed_live_store_item(context, item_def_id="bread", quantity=3)
    seed_player_gold(context, 9999)
    return runtime, context


class TestBuyCommand:
    def test_buy_returns_commerce_command_type(self):
        runtime, context = _setup_campaign(seed=110)
        result = _commerce_command(runtime, context, "buy bread")
        assert result["command_type"] == "commerce"

    def test_buy_adds_item_and_spends_gold(self):
        runtime, context = _setup_campaign(seed=111)
        quantity_before = inventory_quantity(context, "bread")
        gold_before = _player_gold(context)

        result = _commerce_command(runtime, context, "buy bread")

        quantity_after = inventory_quantity(context, "bread")
        gold_after = _player_gold(context)
        assert result["command_type"] == "commerce"
        assert quantity_after == quantity_before + 1
        assert gold_after < gold_before

    def test_buy_does_not_fall_through_to_unknown(self):
        runtime, context = _setup_campaign(seed=112)
        result = _commerce_command(runtime, context, "buy nonexistent_item_xyz")
        assert result["command_type"] == "commerce"
        assert result["command_type"] != "unknown"


class TestSellCommand:
    def test_sell_returns_commerce_command_type(self):
        runtime, context = _setup_campaign(seed=113)
        result = _commerce_command(runtime, context, "sell nonexistent_item_xyz")
        assert result["command_type"] == "commerce"

    def test_sell_returns_gold_and_removes_item_from_inventory(self):
        runtime, context = _setup_campaign(seed=114)

        buy_result = _commerce_command(runtime, context, "buy bread")
        quantity_after_buy = inventory_quantity(context, "bread")
        gold_after_buy = _player_gold(context)

        player = context.kernel_runtime["actors"]["player"]
        item_instance = next(item for item in player.inventory if getattr(item, "item_def_id", "") == "bread")
        store = context.kernel_runtime["stores"][0]
        ok, msg, price = sell_item(player, store, item_instance, commerce_commands._item_registry())
        quantity_after_sell = inventory_quantity(context, "bread")
        gold_after_sell = _player_gold(context)

        assert buy_result["command_type"] == "commerce"
        assert ok is True
        assert isinstance(msg, str)
        assert isinstance(price, int)
        assert quantity_after_buy > 0
        assert quantity_after_sell == quantity_after_buy - 1
        assert gold_after_sell > gold_after_buy

    def test_sell_does_not_fall_through_to_unknown(self):
        runtime, context = _setup_campaign(seed=115)
        result = _commerce_command(runtime, context, "sell nonexistent_item_xyz")
        assert result["command_type"] == "commerce"


class TestServiceCommands:
    def test_rent_room_returns_commerce_type(self):
        runtime, context = _setup_campaign(seed=116)
        result = _commerce_command(runtime, context, "rent room")
        assert result["command_type"] == "commerce"

    def test_rent_a_room_returns_commerce_type(self):
        runtime, context = _setup_campaign(seed=117)
        result = _commerce_command(runtime, context, "rent a room")
        assert result["command_type"] == "commerce"

    def test_identify_returns_commerce_type(self):
        runtime, context = _setup_campaign(seed=118)
        result = _commerce_command(runtime, context, "identify mystery_ring")
        assert result["command_type"] == "commerce"


class TestCommerceRouting:
    """All recognized commerce verbs must route to commerce, never unknown."""

    def test_commerce_verb_never_unknown(self):
        commands = [
            "buy bread",
            "sell nonexistent_item",
            "rent room",
            "rent a room",
            "identify sword",
            "identify strange ring",
        ]
        runtime, context = _setup_campaign(seed=119)
        for command in commands:
            result = _commerce_command(runtime, context, command)
            assert result["command_type"] != "unknown", (
                f"Commerce command '{command}' fell through to unknown"
            )
