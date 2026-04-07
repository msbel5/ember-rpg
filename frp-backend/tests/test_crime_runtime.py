from __future__ import annotations

from engine.api.campaign.crime import current_crime_state
from engine.api.campaign.live_kernel import ensure_kernel_runtime
from engine.api.campaign.runtime import CampaignRuntime
from engine.api.combat_bridge import maybe_handle_combat_command
from engine.api.exploration_bridge import maybe_handle_scene_verb_command
from engine.kernel.actor_records import create_monster_actor
from engine.world import WorldState
from engine.world.consequence import CascadeEngine


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="CrimeRuntime", player_class="rogue", seed=42)
    ensure_kernel_runtime(context)
    if context.world_state is None:
        context.world_state = WorldState(game_id=context.campaign_id)
    if context.cascade_engine is None:
        context.cascade_engine = CascadeEngine()
    return runtime, context


def _isolate_runtime_actors(context) -> None:
    player = context.kernel_runtime["actors"]["player"]
    context.kernel_runtime["actors"] = {"player": player}
    context.entities = {}


def _inject_npc(
    context,
    *,
    actor_id: str,
    name: str,
    role: str,
    position: tuple[int, int],
    hostile: bool = False,
) -> object:
    template = {
        "id": actor_id,
        "name": name,
        "type": "monster",
        "hp": 12,
        "armor_class": 8,
        "cr": 0.25,
        "stats": {"MIG": 8, "AGI": 8, "END": 10, "MND": 8, "INS": 8, "PRE": 6},
        "attacks": [{"name": "club", "attack_bonus": 1, "damage": "1d4"}],
    }
    actor = create_monster_actor(template, faction_id="town_test")
    actor.identity.actor_type = "npc"
    actor.identity.faction_id = "town_test"
    actor.position.x = int(position[0])
    actor.position.y = int(position[1])
    actor.raw_payload["hostile"] = bool(hostile)
    actor.raw_payload["disposition"] = "hostile" if hostile else "friendly"
    actor.raw_payload["role"] = role
    actor.raw_payload["template"] = role
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    context.entities[actor.identity.actor_id] = {
        "name": actor.identity.display_name,
        "role": role,
        "template": role,
        "position": [int(position[0]), int(position[1])],
        "attitude": "hostile" if hostile else "friendly",
        "disposition": "hostile" if hostile else "friendly",
    }
    return actor


def test_raw_theft_records_theft_incident() -> None:
    runtime, context = _make_campaign()
    store = context.kernel_runtime["stores"][0]
    item_id = str(store.items[0].item_def_id)

    result = runtime.run_command(context.campaign_id, f"steal {item_id}")
    incident = result["campaign"]["crime_state"]["last_incident"]

    assert result["command_type"] == "commerce"
    assert incident is not None
    assert incident["crime_type"] == "theft"
    assert incident["target_id"] == store.store_id


def test_structured_theft_records_theft_incident() -> None:
    runtime, context = _make_campaign()
    store = context.kernel_runtime["stores"][0]
    item_id = str(store.items[0].item_def_id)

    result = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="commerce",
        args={"action_id": "steal_item", "item_id": item_id, "store_id": store.store_id},
    )
    incident = result["campaign"]["crime_state"]["last_incident"]

    assert result["command_type"] == "commerce"
    assert incident is not None
    assert incident["crime_type"] == "theft"
    assert incident["target_id"] == store.store_id


def test_non_hostile_attack_records_assault_with_deterministic_witness_count() -> None:
    _runtime, context = _make_campaign()
    _isolate_runtime_actors(context)
    player = context.kernel_runtime["actors"]["player"]
    target = _inject_npc(
        context,
        actor_id="crime_target",
        name="Calm Merchant",
        role="merchant",
        position=(int(player.position.x) + 1, int(player.position.y)),
    )
    _inject_npc(
        context,
        actor_id="crime_witness",
        name="Watchful Villager",
        role="resident",
        position=(int(player.position.x) + 2, int(player.position.y)),
    )
    _inject_npc(
        context,
        actor_id="hostile_bystander",
        name="Bandit Lookout",
        role="raider",
        position=(int(player.position.x) + 2, int(player.position.y) + 1),
        hostile=True,
    )

    result = maybe_handle_combat_command(context, f"attack {target.identity.display_name}")
    crime = current_crime_state(context)

    assert result is not None
    assert result[1] == "combat"
    assert crime["last_incident"] is not None
    assert crime["last_incident"]["crime_type"] == "assault"
    assert crime["witness_count"] == 2


def test_kill_upgrades_assault_to_murder() -> None:
    _runtime, context = _make_campaign()
    _isolate_runtime_actors(context)
    player = context.kernel_runtime["actors"]["player"]
    player.stats["MIG"] = 30
    target = _inject_npc(
        context,
        actor_id="murder_target",
        name="Guarded Merchant",
        role="merchant",
        position=(int(player.position.x) + 1, int(player.position.y)),
    )
    _inject_npc(
        context,
        actor_id="murder_witness",
        name="Street Witness",
        role="resident",
        position=(int(player.position.x) + 2, int(player.position.y)),
    )
    target.hp = 1
    target.max_hp = 1

    for tick in range(40):
        context.kernel_runtime["game_state"].world_time.game_tick = tick
        context.kernel_runtime["game_state"].raw_payload.pop("combat", None)
        maybe_handle_combat_command(context, f"attack {target.identity.display_name}")
        incident = current_crime_state(context).get("last_incident")
        if incident is not None and incident.get("crime_type") == "murder":
            break

    crime = current_crime_state(context)

    assert target.alive is False
    assert crime["last_incident"] is not None
    assert crime["last_incident"]["crime_type"] == "murder"


def test_successful_locked_entry_records_trespass() -> None:
    _runtime, context = _make_campaign()
    _isolate_runtime_actors(context)
    player = context.kernel_runtime["actors"]["player"]
    player.stats["MIG"] = 40
    _inject_npc(
        context,
        actor_id="door_witness",
        name="Door Witness",
        role="resident",
        position=(int(player.position.x) + 2, int(player.position.y)),
    )
    context.entities["locked_test_door"] = {
        "name": "Locked Door",
        "role": "door",
        "template": "door",
        "locked": True,
        "position": [int(player.position.x) + 1, int(player.position.y)],
    }

    result = maybe_handle_scene_verb_command(context, "open locked door")
    crime = current_crime_state(context)

    assert result is not None
    assert result[1] == "exploration"
    assert crime["last_incident"] is not None
    assert crime["last_incident"]["crime_type"] == "trespass"
