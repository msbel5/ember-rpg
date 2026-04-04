from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.party_bridge import maybe_handle_party_command
from engine.kernel.gameplay import spawn_ground_item_entity


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="RuntimeTester", seed=77)
    return runtime, context


def _inject_companion(
    context,
    *,
    base_id: str,
    name: str,
    role: str,
    hostile: bool = False,
):
    from engine.kernel.actor_records import create_monster_actor

    companion = create_monster_actor(
        {
            "id": base_id,
            "name": name,
            "type": "monster",
            "hp": 12,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="raiders" if hostile else "allies",
    )
    companion.identity.actor_type = "npc"
    companion.raw_payload["role"] = role
    companion.raw_payload["hostile"] = hostile
    context.kernel_runtime["actors"][companion.identity.actor_id] = companion
    return companion


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


def test_recruit_companion_save_load_preserves_party_membership() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_scout", name="Scout Mira", role="scout")

    recruit = maybe_handle_party_command(context, "recruit Scout Mira")
    assert recruit is not None
    assert recruit[1] == "party"

    runtime.save_campaign(context.campaign_id, "party_recruit_slot", "RuntimeTester")
    loaded = runtime.load_campaign("party_recruit_slot")

    assert "player" in loaded.campaign_state["party"]
    assert companion.identity.actor_id in loaded.campaign_state["party"]
    payload = runtime.snapshot(loaded.campaign_id, narrative="loaded")
    assert companion.identity.actor_id in payload["campaign"]["party"]


def test_dismiss_companion_save_load_removes_party_membership() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_warden", name="Warden Holt", role="guard")

    assert maybe_handle_party_command(context, "recruit Warden Holt") is not None
    dismiss = maybe_handle_party_command(context, "dismiss Warden Holt")

    assert dismiss is not None
    assert dismiss[1] == "party"
    runtime.save_campaign(context.campaign_id, "party_dismiss_slot", "RuntimeTester")
    loaded = runtime.load_campaign("party_dismiss_slot")

    assert companion.identity.actor_id not in loaded.campaign_state["party"]
    payload = runtime.snapshot(loaded.campaign_id, narrative="loaded")
    assert companion.identity.actor_id not in payload["campaign"]["party"]


def test_party_members_do_not_break_campaign_payload_shape() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_mage", name="Mage Elira", role="mage")
    assert maybe_handle_party_command(context, "recruit Mage Elira") is not None

    payload = runtime.snapshot(context.campaign_id, narrative="party")

    assert payload["campaign"]["party"][0] == "player"
    assert companion.identity.actor_id in payload["campaign"]["party"]
    assert isinstance(payload["campaign"]["world_entities"], list)
    assert isinstance(payload["campaign"]["player"], dict)


def test_duplicate_recruit_does_not_duplicate_party_ids() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_blade", name="Blade Nera", role="guard")

    first = runtime.run_command(context.campaign_id, "recruit Blade Nera")
    second = runtime.run_command(context.campaign_id, "recruit Blade Nera")

    party = context.kernel_runtime["game_state"].party
    assert first["command_type"] == "party"
    assert second["command_type"] == "party"
    assert "already in the party" in second["narrative"].lower()
    assert party.count(companion.identity.actor_id) == 1
    assert first["campaign"]["party"].count(companion.identity.actor_id) == 1
    assert second["campaign"]["party"].count(companion.identity.actor_id) == 1


def test_cannot_dismiss_player() -> None:
    runtime, context = _make_campaign()

    result = runtime.run_command(context.campaign_id, "dismiss RuntimeTester")

    assert result["command_type"] == "party"
    assert "cannot dismiss the player" in result["narrative"].lower()
    assert context.kernel_runtime["game_state"].party == ["player"]


def test_recruit_hostile_and_invalid_actor_fail_safely() -> None:
    runtime, context = _make_campaign()
    hostile = _inject_companion(context, base_id="companion_raider", name="Raider Voss", role="raider", hostile=True)

    hostile_result = runtime.run_command(context.campaign_id, f"recruit {hostile.identity.display_name}")
    invalid_result = runtime.run_command(context.campaign_id, "recruit Nobody Here")

    assert hostile_result["command_type"] == "party"
    assert "hostile" in hostile_result["narrative"].lower()
    assert hostile.identity.actor_id not in context.kernel_runtime["game_state"].party
    assert invalid_result["command_type"] == "party"
    assert "no recruitable companion matched" in invalid_result["narrative"].lower()


def test_region_projection_rebuild_preserves_allied_party_members() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_mapscout", name="Map Scout Iven", role="scout")

    assert runtime.run_command(context.campaign_id, "recruit Map Scout Iven")["command_type"] == "party"
    refreshed = runtime.run_command(context.campaign_id, "look around")

    assert refreshed["command_type"] == "exploration"
    assert companion.identity.actor_id in context.kernel_runtime["game_state"].party
    record = context.entities.get(companion.identity.actor_id)
    assert record is not None
    assert record.get("attitude") == "ally"
    assert record.get("disposition") == "ally"
    assert companion.identity.actor_id in refreshed["campaign"]["party"]


def test_party_payload_remains_deduplicated_and_stable() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_dupe", name="Dorian Pike", role="guard")

    assert runtime.run_command(context.campaign_id, "recruit Dorian Pike")["command_type"] == "party"
    context.kernel_runtime["game_state"].party = ["player", companion.identity.actor_id, companion.identity.actor_id, "player"]
    context.kernel_runtime["game_state"].inactive_npcs = [companion.identity.actor_id, companion.identity.actor_id, "player"]

    payload = runtime.snapshot(context.campaign_id, narrative="party")

    assert payload["campaign"]["party"] == ["player", companion.identity.actor_id]
    assert context.kernel_runtime["game_state"].party == ["player", companion.identity.actor_id]
    assert companion.identity.actor_id not in context.kernel_runtime["game_state"].inactive_npcs
