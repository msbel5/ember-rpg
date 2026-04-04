from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.gameplay import spawn_ground_item_entity


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime(llm=lambda _prompt: "stub")
    context = runtime.create_campaign(player_name="RuntimeTester", seed=77)
    return runtime, context


def test_run_command_pickup_uses_ground_item_authority() -> None:
    runtime, context = _make_campaign()
    spawn_ground_item_entity(
        context,
        item={"id": "iron_ore", "name": "Iron Ore", "qty": 1},
    )

    result = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert result["command_type"] == "inventory"
    assert "picked up" in result["narrative"].lower()
    assert context.find_inventory_item("iron_ore") is not None
    assert any(item.get("id") == "iron_ore" for item in result["campaign"]["player"]["inventory"])
    assert context.campaign_state.get("ground_items", []) == []


def test_run_command_drop_persists_ground_item_authority_for_next_command() -> None:
    runtime, context = _make_campaign()
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 1}, merge=True)

    drop_result = runtime.run_command(context.campaign_id, "drop iron ore")

    assert drop_result["command_type"] == "inventory"
    assert "dropped" in drop_result["narrative"].lower()
    assert len(context.campaign_state.get("ground_items", [])) == 1

    pickup_result = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert pickup_result["command_type"] == "inventory"
    assert "picked up" in pickup_result["narrative"].lower()
    assert context.find_inventory_item("iron_ore") is not None


def test_run_command_spell_uses_kernel_spell_flow() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.spell_points = 10
    player.raw_payload["max_spell_points"] = 10

    result = runtime.run_command(context.campaign_id, "cast magic missile")

    assert result["command_type"] == "spell"
    assert "magic missile" in result["narrative"].lower()
    assert player.spell_points == 8
    assert int(player.raw_payload.get("last_cast_tick", -1)) >= 0


def test_run_command_repeated_pickup_then_missing() -> None:
    runtime, context = _make_campaign()
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_a")
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_b")

    first = runtime.run_command(context.campaign_id, "pickup iron ore")
    second = runtime.run_command(context.campaign_id, "pickup iron ore")
    third = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert first["command_type"] == "inventory"
    assert second["command_type"] == "inventory"
    assert "nothing to pick up" in third["narrative"].lower()
    stack = context.find_inventory_item("iron_ore")
    assert stack is not None
    assert int(stack.get("qty", 1)) == 2
    assert context.campaign_state.get("ground_items", []) == []


def test_run_command_repeated_drop_then_missing() -> None:
    runtime, context = _make_campaign()
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)

    first = runtime.run_command(context.campaign_id, "drop iron ore")
    second = runtime.run_command(context.campaign_id, "drop iron ore")
    third = runtime.run_command(context.campaign_id, "drop iron ore")

    assert first["command_type"] == "inventory"
    assert second["command_type"] == "inventory"
    assert "don't have" in third["narrative"].lower()
    assert len(context.campaign_state.get("ground_items", [])) == 2


def test_run_command_craft_repeated_missing_ingredients_stays_non_mutating() -> None:
    runtime, context = _make_campaign()
    context.kernel_runtime["actors"]["player"].skills["smithing"] = 15
    baseline_inventory = list(context.player.inventory)

    first = runtime.run_command(context.campaign_id, "craft iron bar")
    second = runtime.run_command(context.campaign_id, "craft iron bar")

    assert first["command_type"] == "craft"
    assert second["command_type"] == "craft"
    assert "missing ingredient" in first["narrative"].lower()
    assert "missing ingredient" in second["narrative"].lower()
    assert context.player.inventory == baseline_inventory


def test_run_command_long_rest_repeatedly_hits_cooldown() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.raw_payload["game_tick"] = 100
    player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) // 2)

    first = runtime.run_command(context.campaign_id, "long rest")
    second = runtime.run_command(context.campaign_id, "long rest")

    assert first["command_type"] == "rest"
    assert first["hours_advanced"] == 8
    assert "cannot take a long rest yet" in second["narrative"].lower()
    assert second["hours_advanced"] == 0


def test_run_command_cast_repeatedly_until_insufficient_points() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.spell_points = 4
    player.raw_payload["max_spell_points"] = 4
    player.raw_payload["game_tick"] = 100

    first = runtime.run_command(context.campaign_id, "cast magic missile")
    player.raw_payload["game_tick"] = 106
    second = runtime.run_command(context.campaign_id, "cast magic missile")
    player.raw_payload["game_tick"] = 112
    third = runtime.run_command(context.campaign_id, "cast magic missile")

    assert first["command_type"] == "spell"
    assert second["command_type"] == "spell"
    assert "not enough spell points" in third["narrative"].lower()
    assert player.spell_points == 0