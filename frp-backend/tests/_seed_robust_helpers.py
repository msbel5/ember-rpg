from __future__ import annotations

from typing import Any

from engine.api import campaign_routes
from engine.api.campaign.knowledge import discover_topics
from engine.data._shared import dialog_defs_registry
from engine.kernel.actor_records import create_monster_actor
from engine.kernel.dialog import DialogDef, DialogStateNode, DialogTransition
from engine.world.entity import Entity, EntityType
from engine.world.rumors import RumorNetwork


CURATED_AUTHORED_SEED = 42


def campaign_context(subject: str | object) -> object:
    if isinstance(subject, str):
        return campaign_routes.campaign_runtime.get_campaign(subject)
    return subject


def ensure_attack_target(subject: str | object, *, actor_id: str = "seed_robust_fang", name: str = "Seed Robust Fang", role: str = "wolf") -> dict[str, str]:
    context = campaign_context(subject)
    actor = context.kernel_runtime["actors"].get(actor_id)
    if actor is None:
        actor = create_monster_actor(
            {
                "id": actor_id,
                "name": name,
                "type": "monster",
                "hp": 12,
                "armor_class": 10,
                "cr": 0.125,
                "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
                "attacks": [{"name": "scratch", "attack_bonus": 1, "damage": "1d4"}],
            },
            faction_id="raiders",
        )
        actor.identity.actor_type = "npc"
        actor.raw_payload["role"] = role
        actor.raw_payload["template"] = role
        actor.raw_payload["hostile"] = True
        actor.raw_payload["disposition"] = "hostile"
        context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    target_x, target_y = _free_adjacent_position(context)
    _project_actor_entity(
        context,
        actor,
        position=(target_x, target_y),
        attitude="hostile",
        disposition="hostile",
        context_actions=["attack", "examine"],
    )
    return {"actor_id": str(actor.identity.actor_id), "name": str(actor.identity.display_name)}


def ensure_talkable_authored_dialog_target(
    subject: str | object,
    *,
    actor_id: str = "seed_robust_scholar",
    name: str = "Seed Robust Scholar",
    role: str = "scholar",
) -> dict[str, str]:
    context = campaign_context(subject)
    actor = context.kernel_runtime["actors"].get(actor_id)
    if actor is None:
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
        actor.raw_payload["template"] = role
        actor.raw_payload["memory_id"] = actor_id
        actor.raw_payload["relationship_score"] = 0
        context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    target_x, target_y = _free_adjacent_position(context)
    _project_actor_entity(
        context,
        actor,
        position=(target_x, target_y),
        attitude="friendly",
        disposition="friendly",
        context_actions=["talk", "examine"],
    )
    dialog_def = DialogDef(
        dialog_id=str(actor.identity.actor_id),
        npc_id=str(actor.identity.actor_id),
        states=[
            DialogStateNode(
                state_id="start",
                text=f"{name} studies the road ahead.",
                transitions=[
                    DialogTransition(transition_id="ask_road", text="What do you know?", next_state_id="road"),
                    DialogTransition(transition_id="leave", text="Leave", terminates=True),
                ],
            ),
            DialogStateNode(
                state_id="road",
                text="Keep your eyes on the eastern road.",
                transitions=[DialogTransition(transition_id="leave", text="Leave", terminates=True)],
            ),
        ],
    )
    context.kernel_runtime.setdefault("dialog_defs", {})[dialog_def.dialog_id] = dialog_def
    dialog_defs_registry()[dialog_def.dialog_id] = dialog_def.to_dict()
    return {"actor_id": str(actor.identity.actor_id), "name": str(actor.identity.display_name)}


def ensure_ask_about_topic(subject: str | object, *, actor_id: str, actor_name: str) -> str:
    context = campaign_context(subject)
    rumor_network = context.rumor_network or RumorNetwork()
    context.rumor_network = rumor_network
    rumor = rumor_network.add_rumor("The east road is watched by patrols", actor_name, str(context.region_snapshot.region_id))
    rumor.heard_by.add(actor_id)
    memory = context.npc_memory.get_memory(actor_id, actor_name)
    memory.add_known_fact("The east road is watched by patrols")
    topic_id = f"rumor.{rumor.rumor_id}"
    discover_topics(context, [topic_id])
    return topic_id


def ensure_entity_presence(subject: str | object) -> None:
    context = campaign_context(subject)
    if context.entities:
        return
    actor = create_monster_actor(
        {
            "id": "seed_robust_observer",
            "name": "Seed Robust Observer",
            "type": "monster",
            "hp": 10,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="allies",
    )
    actor.identity.actor_type = "npc"
    actor.raw_payload["role"] = "observer"
    actor.raw_payload["template"] = "observer"
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    target_x, target_y = _free_adjacent_position(context)
    _project_actor_entity(
        context,
        actor,
        position=(target_x, target_y),
        attitude="friendly",
        disposition="friendly",
        context_actions=["talk", "examine"],
    )


def open_curated_authored_dialog(runtime: Any, context: object) -> dict[str, Any]:
    snapshot = runtime.snapshot(context.campaign_id, narrative="curated-authored-seed")
    talkables = [
        entity
        for entity in snapshot["campaign"].get("world_entities", [])
        if entity.get("entity_type") == "npc" and "talk" in entity.get("context_actions", [])
    ]
    assert talkables, f"Expected at least one talkable NPC on curated seed {CURATED_AUTHORED_SEED}"
    for talkable in talkables:
        target_name = str(talkable["name"])
        position = talkable["position"]
        move_x = max(0, int(position[0]) - 3)
        move_y = int(position[1])
        runtime.run_command(context.campaign_id, f"move to {move_x},{move_y}")
        opened = runtime.run_command(context.campaign_id, f"talk {target_name}")
        if opened.get("dialog_npc") == target_name and opened.get("command_type") == "dialog":
            return {"entity": talkable, "response": opened}
    raise AssertionError(f"Expected an authored dialog opening on curated seed {CURATED_AUTHORED_SEED}")


def _free_adjacent_position(context: object) -> tuple[int, int]:
    player = context.kernel_runtime["actors"]["player"]
    occupied: set[tuple[int, int]] = set()
    for record in context.entities.values():
        if not isinstance(record, dict):
            continue
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) == 2:
            occupied.add((int(position[0]), int(position[1])))
    anchor_x = int(player.position.x)
    anchor_y = int(player.position.y)
    for dx, dy in ((1, 0), (0, 1), (0, -1), (-1, 0), (2, 0)):
        candidate = (anchor_x + dx, anchor_y + dy)
        if candidate not in occupied:
            return candidate
    return anchor_x + 1, anchor_y


def _project_actor_entity(
    context: object,
    actor: object,
    *,
    position: tuple[int, int],
    attitude: str,
    disposition: str,
    context_actions: list[str],
) -> None:
    actor.position.x = int(position[0])
    actor.position.y = int(position[1])
    entity = Entity(
        id=actor.identity.actor_id,
        entity_type=EntityType.NPC,
        name=actor.identity.display_name,
        position=(int(position[0]), int(position[1])),
        glyph="!" if attitude == "hostile" else "A",
        color="red" if attitude == "hostile" else "light_blue",
        blocking=True,
        hp=int(actor.stats.get("hp", 1)),
        max_hp=int(actor.stats.get("max_hp", actor.stats.get("hp", 1))),
        disposition=disposition,
        attitude=attitude,
        faction=getattr(actor.identity, "faction_id", None),
        job=str(actor.raw_payload.get("role", "npc")),
    )
    if context.spatial_index.get_position(actor.identity.actor_id) is None:
        context.spatial_index.add(entity)
    context.entities[actor.identity.actor_id] = {
        "name": actor.identity.display_name,
        "type": "npc",
        "position": [int(position[0]), int(position[1])],
        "faction": getattr(actor.identity, "faction_id", None),
        "role": str(actor.raw_payload.get("role", "npc")),
        "attitude": attitude,
        "disposition": disposition,
        "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", "npc"))),
        "context_actions": list(context_actions),
        "entity_ref": entity,
    }
