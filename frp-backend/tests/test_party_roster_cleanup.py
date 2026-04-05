from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.world.entity import Entity, EntityType


def _make_campaign():
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="RosterTester", seed=91)
    return runtime, context


def _inject_companion(context, *, actor_id: str, name: str, role: str):
    from engine.kernel.actor_records import create_monster_actor

    actor = create_monster_actor(
        {
            "id": actor_id,
            "name": name,
            "type": "monster",
            "hp": 12,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="allies",
    )
    actor.identity.actor_type = "npc"
    actor.raw_payload["role"] = role
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    return actor


def _inject_prop_like_actor(context, *, actor_id: str, name: str, role: str = "cabinet"):
    from engine.kernel.actor_records import create_monster_actor

    actor = create_monster_actor(
        {
            "id": actor_id,
            "name": name,
            "type": "monster",
            "hp": 1,
            "armor_class": 5,
            "stats": {"MIG": 1, "AGI": 1, "END": 1, "MND": 1, "INS": 1, "PRE": 1},
        },
        faction_id="neutral",
    )
    actor.identity.actor_type = "npc"
    actor.raw_payload["role"] = role
    actor.raw_payload["companion_roster"] = True
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    entity = Entity(
        id=actor.identity.actor_id,
        entity_type=EntityType.FURNITURE,
        name=name,
        position=(int(context.position[0]) + 1, int(context.position[1])),
        glyph="#",
        color="orange",
        blocking=False,
        hp=1,
        max_hp=1,
        disposition="neutral",
        job=role,
    )
    if context.spatial_index.get_position(actor.identity.actor_id) is None:
        context.spatial_index.add(entity)
    context.entities[actor.identity.actor_id] = {
        "name": name,
        "type": "furniture",
        "position": [entity.position[0], entity.position[1]],
        "role": role,
        "template": role,
        "context_actions": ["examine"],
        "entity_ref": entity,
    }
    return actor


def test_recruiting_valid_companion_does_not_pollute_reserve_roster_with_props() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, actor_id="companion_scout_iven", name="Scout Iven", role="scout")
    prop = _inject_prop_like_actor(context, actor_id="prop_cabinet", name="Cabinet")

    recruit = runtime.run_command(context.campaign_id, "recruit Scout Iven")
    party_view = runtime.run_command(context.campaign_id, "party")

    assert recruit["command_type"] == "party"
    assert companion.identity.actor_id in context.kernel_runtime["game_state"].party
    assert prop.identity.actor_id not in context.kernel_runtime["game_state"].inactive_npcs
    assert prop.identity.actor_id not in context.campaign_state.get("reserve_party_members", [])
    assert "Cabinet" not in party_view["narrative"]


def test_prop_named_target_is_not_recruitable() -> None:
    runtime, context = _make_campaign()
    prop = _inject_prop_like_actor(context, actor_id="prop_table", name="Table", role="table")

    result = runtime.run_command(context.campaign_id, "recruit Table")

    assert result["command_type"] == "party"
    assert "no recruitable companion matched" in result["narrative"].lower()
    assert prop.identity.actor_id not in context.kernel_runtime["game_state"].party
    assert prop.identity.actor_id not in context.kernel_runtime["game_state"].inactive_npcs


def test_save_load_preserves_clean_active_and_reserve_party_state() -> None:
    runtime, context = _make_campaign()
    active = _inject_companion(context, actor_id="companion_active_rowan", name="Active Rowan", role="guard")
    reserve = _inject_companion(context, actor_id="companion_reserve_quinn", name="Reserve Quinn", role="scout")
    prop = _inject_prop_like_actor(context, actor_id="prop_oven", name="Oven", role="oven")

    assert runtime.run_command(context.campaign_id, "recruit Active Rowan")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "recruit Reserve Quinn")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "dismiss Reserve Quinn")["command_type"] == "party"

    runtime.save_campaign(context.campaign_id, "party_roster_cleanup_slot", "RosterTester")
    loaded = runtime.load_campaign("party_roster_cleanup_slot")
    payload = runtime.snapshot(loaded.campaign_id, narrative="loaded")

    assert active.identity.actor_id in loaded.kernel_runtime["game_state"].party
    assert reserve.identity.actor_id in loaded.kernel_runtime["game_state"].inactive_npcs
    assert prop.identity.actor_id not in loaded.kernel_runtime["game_state"].inactive_npcs
    assert prop.identity.actor_id not in loaded.campaign_state.get("reserve_party_members", [])
    assert "Oven" not in payload["campaign"]["party"]
