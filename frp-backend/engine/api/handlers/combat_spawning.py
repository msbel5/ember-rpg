"""Combat bootstrap and enemy spawning helpers -- kernel-native edition.

All actor creation and combat state management uses kernel types directly.
No engine.core imports are used anywhere in this module.
"""
from __future__ import annotations

import random
from typing import Any, Optional

from engine.api.session.core import GameSession
from engine.kernel.actor_records import (
    ActorRecord,
    create_monster_actor,
    create_player_actor,
)
from engine.kernel.combat_engine import CombatState, start_combat, start_turn
from engine.kernel.narrator import SceneType
from engine.data_loader import list_monsters
from engine.world.body_parts import BodyPartTracker
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds


class CombatSpawningMixin:
    """Focused helpers for creating enemies and bootstrapping encounters."""

    def _spawn_guard_backup(self, session: GameSession) -> ActorRecord:
        """Create a generic town guard as an ActorRecord.

        Uses Ember stat keys directly — no D&D translation needed.
        """
        template: dict[str, Any] = {
            "id": "town_guard",
            "name": "Town Guard",
            "hp": 12,
            "armor_class": 14,
            "type": "guard",
            "cr": 0.5,
            "stats": {"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 12},
            "attacks": [{"attack_bonus": 3}],
            "loot_table": [],
        }
        guard = create_monster_actor(
            template,
            position=tuple(session.position),
            faction_id="town",
        )
        return guard

    def _start_combat(self, session: GameSession, enemies: list[ActorRecord]) -> None:
        """Bootstrap a combat encounter with kernel types.

        Registers enemy entities in the spatial index, builds a
        combat_actors lookup dict, and stores a CombatState in
        session.campaign_state instead of legacy CombatManager.
        """
        # Ensure campaign_state sub-dicts exist.
        if "combat_actors" not in session.campaign_state:
            session.campaign_state["combat_actors"] = {}
        combat_actors: dict[str, ActorRecord] = session.campaign_state["combat_actors"]

        # Build or retrieve the player ActorRecord.
        player_actor = combat_actors.get("player")
        if player_actor is None:
            # session.player is always an ActorRecord — read directly
            player = session.player
            if player is not None:
                player_actor = create_player_actor(
                    name=player.name,
                    class_name=player.dominant_class,
                    stats=dict(player.stats),
                    level=player.level,
                    actor_id="player",
                    position=tuple(session.position),
                )
                # Preserve actual HP from the live ActorRecord
                player_actor.stats["hp"] = player.hp
                player_actor.stats["max_hp"] = player.max_hp
            else:
                from engine.data_loader import get_creation_default_class
                player_actor = create_player_actor(
                    name="Player",
                    class_name=get_creation_default_class(),
                    stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
                    actor_id="player", position=tuple(session.position),
                )
        combat_actors["player"] = player_actor

        # Register each enemy in the spatial index and entity dict.
        adjacent_positions = [
            (session.position[0] + 1, session.position[1]),
            (session.position[0] - 1, session.position[1]),
            (session.position[0], session.position[1] + 1),
            (session.position[0], session.position[1] - 1),
        ]
        for enemy in enemies:
            actor_id = enemy.identity.actor_id
            combat_actors[actor_id] = enemy

            if actor_id not in session.entities:
                spawn_pos = list(session.position)
                for candidate in adjacent_positions:
                    if session.map_data is not None and not session.map_data.is_walkable(*candidate):
                        continue
                    blockers = session.spatial_index.at(*candidate) if session.spatial_index is not None else []
                    if any(getattr(b, "blocking", False) for b in blockers):
                        continue
                    spawn_pos = [candidate[0], candidate[1]]
                    break

                role = enemy.raw_payload.get("monster_type", "monster")
                live_entity = Entity(
                    id=actor_id,
                    entity_type=EntityType.NPC,
                    name=enemy.name,
                    position=tuple(spawn_pos),
                    glyph="g",
                    color="red",
                    blocking=True,
                    hp=enemy.hp,
                    max_hp=enemy.max_hp,
                    disposition="hostile",
                    attitude="hostile",
                    alignment="CE",
                    body=BodyPartTracker(),
                    needs=NPCNeeds(safety=30, commerce=5, social=10, sustenance=70, duty=60),
                    job=str(role),
                )
                if session.spatial_index is not None and session.spatial_index.get_position(actor_id) is None:
                    session.spatial_index.add(live_entity)
                session.entities[actor_id] = {
                    "name": enemy.name,
                    "type": "npc",
                    "position": list(spawn_pos),
                    "role": role,
                    "faction": "hostile",
                    "hp": enemy.hp,
                    "max_hp": enemy.max_hp,
                    "alive": True,
                    "blocking": True,
                    "attitude": "hostile",
                    "alignment": "CE",
                    "alignment_axes": {"law_chaos": -40, "good_evil": -40},
                    "body": live_entity.body,
                    "needs": live_entity.needs,
                    "entity_ref": live_entity,
                }
                session.sync_entity_record(actor_id, live_entity)

        # Build ordered actor list and start kernel combat.
        all_actors = [player_actor] + list(enemies)
        combat_state = start_combat(all_actors, seed=random.randint(0, 9999))
        # Kick off the first turn.
        start_turn(combat_state, combat_actors)

        # Store kernel combat state (session.combat is NOT used for kernel combat).
        session.campaign_state["combat_state"] = combat_state

        session.clear_conversation_target()
        self.dm.transition(session.dm_context, SceneType.COMBAT)

    def _spawn_enemy(self, player_level: int, preferred_name: Optional[str] = None) -> ActorRecord:
        """Select and create an enemy ActorRecord from monster data.

        Loads monster templates via list_monsters(), picks the best
        match by name or challenge rating, then builds an ActorRecord
        using create_monster_actor() -- no legacy Character needed.
        """
        monsters = list_monsters()
        query = str(preferred_name or "").strip().lower()
        selected: Optional[dict[str, Any]] = None

        # Try to match by name or id.
        if query:
            for monster in monsters:
                monster_id = str(monster.get("id", "")).lower()
                monster_name = str(monster.get("name", "")).lower()
                if query in monster_id or query in monster_name:
                    selected = monster
                    break

        # Fall back to CR-based selection.
        if selected is None:
            target_cr = max(0.25, float(player_level) * 0.5)
            ranked = sorted(
                monsters,
                key=lambda m: (abs(float(m.get("cr", 0.25)) - target_cr), str(m.get("name", ""))),
            )
            pool = ranked[: max(1, min(6, len(ranked)))]
            selected = random.choice(pool) if pool else (monsters[0] if monsters else {})

        # Delegate to kernel factory -- handles D&D-to-Ember stat mapping.
        return create_monster_actor(selected)
