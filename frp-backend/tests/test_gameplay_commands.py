"""Tests for gameplay command handlers (equipment, inventory, craft, rest, spell)."""
from __future__ import annotations


from engine.api.campaign.runtime import CampaignRuntime
from engine.api.gameplay_bridge import (
    _find_inventory_item_by_name,
    maybe_handle_craft_command,
    maybe_handle_equipment_command,
    maybe_handle_inventory_command,
    maybe_handle_item_use_command,
    maybe_handle_rest_command,
    maybe_handle_spell_command,
)
from engine.kernel.gameplay import spawn_ground_item_entity
from engine.world.entity import Entity, EntityType


def _make_campaign():
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="TestPlayer", seed=42)
    return rt, ctx


def _player_actor(ctx):
    return ctx.kernel_runtime["actors"]["player"]


def _count_actor_item_quantity(actor, item_def_id: str) -> int:
    return sum(
        max(1, int(getattr(item, "quantity", 1)))
        for item in actor.inventory
        if getattr(item, "item_def_id", "") == item_def_id
    )


def _add_inventory_item(actor, item_def_id: str, *, quantity: int = 1, payload: dict | None = None):
    from engine.kernel.actor_items import ItemStack

    item_payload = {
        "id": item_def_id,
        "item_def_id": item_def_id,
        "name": item_def_id.replace("_", " ").title(),
        "quantity": quantity,
        "qty": quantity,
        **dict(payload or {}),
    }
    stack = ItemStack(
        instance_id=f"{item_def_id}_{len(actor.inventory)}",
        item_def_id=item_def_id,
        quantity=quantity,
        payload=item_payload,
    )
    actor.inventory.append(stack)
    return stack


def _add_workstation(ctx, *, workstation_id: str, name: str, offset: tuple[int, int] = (1, 0)) -> None:
    x = int(ctx.position[0]) + int(offset[0])
    y = int(ctx.position[1]) + int(offset[1])
    entity = Entity(
        id=workstation_id,
        entity_type=EntityType.FURNITURE,
        name=name,
        position=(x, y),
        glyph="#",
        color="orange",
        blocking=False,
        hp=1,
        max_hp=1,
        disposition="neutral",
        job=name.lower().replace(" ", "_"),
    )
    ctx.spatial_index.add(entity)
    ctx.entities[workstation_id] = {
        "name": name,
        "type": "furniture",
        "position": [x, y],
        "role": name.lower().replace(" ", "_"),
        "template": name.lower().replace(" ", "_"),
        "context_actions": ["examine", "use"],
        "entity_ref": entity,
    }


# ---------------------------------------------------------------------------
# Equipment handler
# ---------------------------------------------------------------------------

class TestEquipCommand:

    def test_equip_command_recognized(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        # Add an item to inventory so equip can find it.
        from engine.kernel.actor_items import ItemStack
        player.inventory.append(ItemStack(
            instance_id="test_sword_001",
            item_def_id="iron_shortsword",
            quantity=1,
        ))
        result = maybe_handle_equipment_command(ctx, "equip iron_shortsword")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "equipment"
        assert hours == 0
        assert isinstance(narrative, str)
        assert len(narrative) > 0

    def test_equip_missing_item_returns_message(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_equipment_command(ctx, "equip nonexistent_blade")
        assert result is not None
        narrative, cmd_type, _hours = result
        assert "don't have" in narrative.lower() or "inventory" in narrative.lower()
        assert cmd_type == "equipment"


class TestUnequipCommand:

    def test_unequip_command_recognized(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        # Place an item in an equipment slot.
        from engine.kernel.actor_items import ItemStack
        sword = ItemStack(
            instance_id="test_sword_002",
            item_def_id="iron_shortsword",
            quantity=1,
        )
        player.equipment.slots.setdefault("weapon_1", []).append(sword)
        result = maybe_handle_equipment_command(ctx, "unequip iron_shortsword")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "equipment"
        assert hours == 0
        assert isinstance(narrative, str)

    def test_unequip_nothing_equipped(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_equipment_command(ctx, "unequip phantom_armor")
        assert result is not None
        narrative, _cmd_type, _hours = result
        assert "no equipped" in narrative.lower() or "not found" in narrative.lower()


# ---------------------------------------------------------------------------
# Inventory handler
# ---------------------------------------------------------------------------

class TestPickupCommand:

    def test_pickup_command_recognized(self):
        _rt, ctx = _make_campaign()
        count_before = len(ctx.player.inventory)
        spawn_ground_item_entity(
            ctx,
            item={"id": "healing_potion", "name": "Healing Potion", "qty": 1},
        )
        result = maybe_handle_inventory_command(ctx, "pickup healing_potion")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "inventory"
        assert hours == 0
        assert "picked up" in narrative.lower()
        assert len(ctx.player.inventory) == count_before + 1
        assert ctx.find_inventory_item("healing_potion") is not None
        assert ctx.campaign_state.get("ground_items", []) == []

    def test_take_alias_recognized(self):
        _rt, ctx = _make_campaign()
        spawn_ground_item_entity(
            ctx,
            item={"id": "iron_ore", "name": "Iron Ore", "qty": 1},
        )
        result = maybe_handle_inventory_command(ctx, "take iron_ore")
        assert result is not None
        assert result[1] == "inventory"

    def test_pickup_missing_ground_item_returns_message(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_inventory_command(ctx, "pickup iron_ore")
        assert result is not None
        assert "nothing to pick up" in result[0].lower()

    def test_pickup_repeated_ground_items_stacks_into_inventory(self):
        _rt, ctx = _make_campaign()
        spawn_ground_item_entity(ctx, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_a")
        spawn_ground_item_entity(ctx, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_b")

        first = maybe_handle_inventory_command(ctx, "pickup iron_ore")
        second = maybe_handle_inventory_command(ctx, "pickup iron ore")
        third = maybe_handle_inventory_command(ctx, "pickup iron ore")

        assert first is not None and "picked up" in first[0].lower()
        assert second is not None and "picked up" in second[0].lower()
        assert third is not None and "nothing to pick up" in third[0].lower()
        stack = ctx.find_inventory_item("iron_ore")
        assert stack is not None
        assert int(stack.get("qty", 1)) == 2
        assert ctx.campaign_state.get("ground_items", []) == []


class TestDropCommand:

    def test_drop_command_recognized(self):
        _rt, ctx = _make_campaign()
        ctx.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 1}, merge=True)
        count_before = len(ctx.player.inventory)
        result = maybe_handle_inventory_command(ctx, "drop iron_ore")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "inventory"
        assert hours == 0
        assert "dropped" in narrative.lower()
        assert len(ctx.player.inventory) == count_before - 1
        ground_items = ctx.campaign_state.get("ground_items", [])
        assert len(ground_items) == 1
        assert ground_items[0]["name"] == "Iron Ore"

    def test_drop_missing_item(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_inventory_command(ctx, "drop unicorn_horn")
        assert result is not None
        assert "don't have" in result[0].lower()

    def test_drop_repeated_items_until_inventory_empty(self):
        _rt, ctx = _make_campaign()
        ctx.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)

        first = maybe_handle_inventory_command(ctx, "drop iron ore")
        second = maybe_handle_inventory_command(ctx, "drop iron_ore")
        third = maybe_handle_inventory_command(ctx, "drop iron ore")

        assert first is not None and "dropped" in first[0].lower()
        assert second is not None and "dropped" in second[0].lower()
        assert third is not None and "don't have" in third[0].lower()
        assert ctx.find_inventory_item("iron_ore") is None
        assert len(ctx.campaign_state.get("ground_items", [])) == 2


# ---------------------------------------------------------------------------
# Item use handler
# ---------------------------------------------------------------------------


class TestUseItemCommand:

    def test_use_healing_consumable_on_self(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) - 8)
        _add_inventory_item(
            player,
            "field_tonic",
            payload={"name": "Field Tonic", "type": "consumable", "heal": 8},
        )

        result = maybe_handle_item_use_command(ctx, "use field tonic")

        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "inventory"
        assert hours == 0
        assert "used field tonic" in narrative.lower()
        assert int(player.stats["hp"]) > max(1, int(player.stats.get("max_hp", 20)) - 8)
        assert _find_inventory_item_by_name(player, "field_tonic") is None

    def test_use_wand_decrements_charges_without_destroying_until_empty(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) - 6)
        wand = _add_inventory_item(
            player,
            "wand_of_healing",
            payload={"name": "Wand of Healing", "charges": 2, "identified": True},
        )

        first = maybe_handle_item_use_command(ctx, "use wand of healing")
        second = maybe_handle_item_use_command(ctx, "use wand of healing")
        third = maybe_handle_item_use_command(ctx, "use wand of healing")

        assert first is not None and "1 charges remain" in first[0].lower()
        assert second is not None and "0 charges remain" in second[0].lower()
        assert third is not None and "no charges" in third[0].lower()
        assert wand in player.inventory
        assert int(wand.payload.get("charges", -1)) == 0

    def test_use_non_usable_equipment_fails_without_mutation(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        ring = _add_inventory_item(
            player,
            "ring_of_protection",
            payload={"name": "Ring of Protection", "identified": False},
        )
        quantity_before = int(ring.quantity)

        result = maybe_handle_item_use_command(ctx, "use ring of protection")

        assert result is not None
        assert "cannot be used this way" in result[0].lower()
        assert ring in player.inventory
        assert int(ring.quantity) == quantity_before
        assert bool(ring.payload.get("identified", False)) is False

    def test_use_item_on_named_target(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        target = next(
            actor
            for actor_id, actor in ctx.kernel_runtime["actors"].items()
            if actor_id != "player"
        )
        target.stats["hp"] = max(1, int(target.stats.get("max_hp", 10)) - 5)
        _add_inventory_item(
            player,
            "field_tonic",
            payload={"name": "Field Tonic", "type": "consumable", "heal": 6},
        )

        result = maybe_handle_item_use_command(ctx, f"use field tonic on {target.name}")

        assert result is not None
        assert result[1] == "inventory"
        assert int(target.stats["hp"]) > max(1, int(target.stats.get("max_hp", 10)) - 5)
        assert target.name.lower() in result[0].lower()

    def test_runtime_dispatch_supports_use_item_command(self):
        runtime, context = _make_campaign()
        player = _player_actor(context)
        player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) - 4)
        _add_inventory_item(
            player,
            "field_tonic",
            payload={"name": "Field Tonic", "type": "consumable", "heal": 4},
        )

        response = runtime.run_command(context.campaign_id, "use field tonic")

        assert response["command_type"] == "inventory"
        assert "used field tonic" in response["narrative"].lower()
        assert int(response["campaign"]["player"]["hp"]) >= int(player.stats["hp"])

    def test_use_item_state_survives_save_load(self):
        runtime, context = _make_campaign()
        player = _player_actor(context)
        _add_inventory_item(
            player,
            "wand_of_healing",
            payload={"name": "Wand of Healing", "charges": 3, "identified": False},
        )

        runtime.save_campaign(context.campaign_id, "magic_item_slot", "RuntimeTester")
        loaded = runtime.load_campaign("magic_item_slot")
        loaded_player = loaded.kernel_runtime["actors"]["player"]
        wand = _find_inventory_item_by_name(loaded_player, "wand_of_healing")

        assert wand is not None
        assert bool(wand.payload.get("identified", True)) is False
        assert int(wand.payload.get("charges", -1)) == 3


# ---------------------------------------------------------------------------
# Craft handler
# ---------------------------------------------------------------------------

class TestCraftCommand:

    def test_craft_command_recognized(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        _add_workstation(ctx, workstation_id="test_forge_recognized", name="Practice Forge")
        # Give player the ingredients for iron_bar: 2x iron_ore + 1x coal.
        from engine.kernel.actor_items import ItemStack
        player.inventory.append(ItemStack(
            instance_id="ore1", item_def_id="iron_ore", quantity=1,
        ))
        player.inventory.append(ItemStack(
            instance_id="ore2", item_def_id="iron_ore", quantity=1,
        ))
        player.inventory.append(ItemStack(
            instance_id="coal1", item_def_id="coal", quantity=1,
        ))
        # Grant smithing skill to meet DC.
        player.skills["smithing"] = 15
        result = maybe_handle_craft_command(ctx, "craft iron_bar")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "craft"
        assert hours == 2
        assert "crafted" in narrative.lower()

    def test_craft_unknown_recipe(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_craft_command(ctx, "craft unicorn_saddle")
        assert result is not None
        assert "no recipe" in result[0].lower()

    def test_craft_missing_ingredients(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        _add_workstation(ctx, workstation_id="test_forge_missing", name="Practice Forge")
        player.skills["smithing"] = 15
        result = maybe_handle_craft_command(ctx, "craft iron_bar")
        assert result is not None
        assert "missing" in result[0].lower()

    def test_craft_repeatedly_transitions_inventory(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        _add_workstation(ctx, workstation_id="test_forge_repeated", name="Practice Forge")
        from engine.kernel.actor_items import ItemStack

        for index in range(4):
            player.inventory.append(ItemStack(instance_id=f"ore{index}", item_def_id="iron_ore", quantity=1))
        for index in range(2):
            player.inventory.append(ItemStack(instance_id=f"coal{index}", item_def_id="coal", quantity=1))
        player.skills["smithing"] = 15

        first = maybe_handle_craft_command(ctx, "craft iron bar")
        second = maybe_handle_craft_command(ctx, "craft iron_bar")
        third = maybe_handle_craft_command(ctx, "craft iron bar")

        assert first is not None and "crafted" in first[0].lower()
        assert second is not None and "crafted" in second[0].lower()
        assert third is not None and "missing" in third[0].lower()
        assert _count_actor_item_quantity(player, "iron_ore") == 0
        assert _count_actor_item_quantity(player, "coal") == 0
        assert _count_actor_item_quantity(player, "iron_bar") == 2


# ---------------------------------------------------------------------------
# Rest handler
# ---------------------------------------------------------------------------

class TestRestCommand:

    def test_rest_heals_player(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        max_hp = int(player.stats.get("max_hp", 20))
        player.stats["hp"] = max(1, max_hp - 5)
        hp_before = int(player.stats["hp"])
        result = maybe_handle_rest_command(ctx, "rest")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "rest"
        assert hours == 1
        assert int(player.stats["hp"]) >= hp_before
        assert "healed" in narrative.lower() or "rest" in narrative.lower()

    def test_short_rest_alias(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        max_hp = int(player.stats.get("max_hp", 20))
        player.stats["hp"] = max(1, max_hp - 5)
        result = maybe_handle_rest_command(ctx, "short rest")
        assert result is not None
        assert result[2] == 1  # 1 hour

    def test_long_rest_full_restore(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        max_hp = int(player.stats.get("max_hp", 20))
        player.stats["hp"] = max(1, max_hp // 2)
        result = maybe_handle_rest_command(ctx, "long rest")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "rest"
        assert hours == 8
        assert int(player.stats["hp"]) == int(player.stats["max_hp"])

    def test_sleep_is_long_rest(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        max_hp = int(player.stats.get("max_hp", 20))
        player.stats["hp"] = max(1, max_hp // 2)
        result = maybe_handle_rest_command(ctx, "sleep")
        assert result is not None
        assert result[2] == 8
        assert int(player.stats["hp"]) == int(player.stats["max_hp"])

    def test_repeated_long_rest_hits_cooldown(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.raw_payload["game_tick"] = 100

        first = maybe_handle_rest_command(ctx, "long rest")
        second = maybe_handle_rest_command(ctx, "long rest")

        assert first is not None and first[2] == 8
        assert second is not None
        assert second[2] == 0
        assert "cannot take a long rest yet" in second[0].lower()


# ---------------------------------------------------------------------------
# Spell handler
# ---------------------------------------------------------------------------

class TestSpellCommand:

    def test_spell_command_recognized(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        # Grant spell points so casting works.
        player.spell_points = 10
        player.raw_payload["max_spell_points"] = 10
        result = maybe_handle_spell_command(ctx, "cast magic missile")
        assert result is not None
        narrative, cmd_type, hours = result
        assert cmd_type == "spell"
        assert hours == 1
        assert "casts" in narrative.lower() or "magic missile" in narrative.lower()
        assert player.spell_points == 8

    def test_spell_with_target(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.spell_points = 10
        result = maybe_handle_spell_command(ctx, "cast cure wounds at self")
        assert result is not None
        assert result[1] == "spell"

    def test_spell_not_enough_points(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.spell_points = 0
        result = maybe_handle_spell_command(ctx, "cast fireball")
        assert result is not None
        assert "not enough" in result[0].lower()

    def test_unknown_spell(self):
        _rt, ctx = _make_campaign()
        result = maybe_handle_spell_command(ctx, "cast explodium maximus")
        assert result is not None
        assert "unknown" in result[0].lower()

    def test_spell_repeated_until_insufficient_points(self):
        _rt, ctx = _make_campaign()
        player = _player_actor(ctx)
        player.spell_points = 4
        player.raw_payload["max_spell_points"] = 4
        player.raw_payload["game_tick"] = 100

        first = maybe_handle_spell_command(ctx, "cast magic missile")
        player.raw_payload["game_tick"] = 106
        second = maybe_handle_spell_command(ctx, "cast magic missile")
        player.raw_payload["game_tick"] = 112
        third = maybe_handle_spell_command(ctx, "cast magic missile")

        assert first is not None and first[1] == "spell"
        assert second is not None and second[1] == "spell"
        assert third is not None
        assert "not enough" in third[0].lower()
        assert player.spell_points == 0


# ---------------------------------------------------------------------------
# Non-gameplay commands return None
# ---------------------------------------------------------------------------

class TestNonGameplayReturnsNone:

    def test_non_gameplay_returns_none(self):
        _rt, ctx = _make_campaign()
        assert maybe_handle_equipment_command(ctx, "look around") is None
        assert maybe_handle_inventory_command(ctx, "look around") is None
        assert maybe_handle_item_use_command(ctx, "look around") is None
        assert maybe_handle_craft_command(ctx, "look around") is None
        assert maybe_handle_rest_command(ctx, "look around") is None
        assert maybe_handle_spell_command(ctx, "look around") is None

    def test_empty_command_returns_none(self):
        _rt, ctx = _make_campaign()
        assert maybe_handle_equipment_command(ctx, "") is None
        assert maybe_handle_inventory_command(ctx, "") is None
        assert maybe_handle_item_use_command(ctx, "") is None
        assert maybe_handle_craft_command(ctx, "") is None
        assert maybe_handle_rest_command(ctx, "") is None
        assert maybe_handle_spell_command(ctx, "") is None
