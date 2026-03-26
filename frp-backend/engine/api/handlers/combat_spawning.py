"""Combat bootstrap and enemy spawning helpers."""
from __future__ import annotations

import random
from typing import Any, Optional

from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.dm_agent import SceneType
from engine.data_loader import list_monsters
from engine.world.entity import Entity, EntityType


class CombatSpawningMixin:
    """Focused helpers for creating enemies and bootstrapping encounters."""

    def _spawn_guard_backup(self, session: GameSession) -> Character:
        guard = Character(
            name="Town Guard",
            hp=12,
            max_hp=12,
            stats={"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 12},
        )
        guard.role = "guard"
        return guard

    def _start_combat(self, session: GameSession, enemies: list[Character]) -> None:
        combatants = [session.player]
        adjacent_positions = [
            (session.position[0] + 1, session.position[1]),
            (session.position[0] - 1, session.position[1]),
            (session.position[0], session.position[1] + 1),
            (session.position[0], session.position[1] - 1),
        ]
        for enemy in enemies:
            entity_id = getattr(enemy, "_entity_id", None)
            if not entity_id:
                entity_id = f"combat_enemy_{len(session.entities) + 1}"
                enemy._entity_id = entity_id
            if entity_id not in session.entities:
                spawn_pos = list(session.position)
                for candidate in adjacent_positions:
                    if session.map_data is not None and not session.map_data.is_walkable(*candidate):
                        continue
                    blockers = session.spatial_index.at(*candidate) if session.spatial_index is not None else []
                    if any(getattr(blocker, "blocking", False) for blocker in blockers):
                        continue
                    spawn_pos = [candidate[0], candidate[1]]
                    break
                live_entity = Entity(
                    id=entity_id,
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
                )
                if session.spatial_index is not None and session.spatial_index.get_position(entity_id) is None:
                    session.spatial_index.add(live_entity)
                session.entities[entity_id] = {
                    "name": enemy.name,
                    "type": "npc",
                    "position": list(spawn_pos),
                    "role": getattr(enemy, "role", "monster"),
                    "faction": "hostile",
                    "hp": enemy.hp,
                    "max_hp": enemy.max_hp,
                    "alive": True,
                    "blocking": True,
                    "attitude": "hostile",
                    "alignment": "CE",
                    "alignment_axes": {"law_chaos": -40, "good_evil": -40},
                    "entity_ref": live_entity,
                }
            combatants.append(enemy)
        session.combat = CombatManager(combatants, seed=random.randint(0, 9999))
        session.combat.start_turn()
        session.clear_conversation_target()
        self.dm.transition(session.dm_context, SceneType.COMBAT)

    def _spawn_enemy(self, player_level: int, preferred_name: Optional[str] = None) -> Character:
        monsters = list_monsters()
        query = str(preferred_name or "").strip().lower()
        selected: Optional[dict[str, Any]] = None

        if query:
            for monster in monsters:
                monster_id = str(monster.get("id", "")).lower()
                monster_name = str(monster.get("name", "")).lower()
                if query in monster_id or query in monster_name:
                    selected = monster
                    break

        if selected is None:
            target_cr = max(0.25, float(player_level) * 0.5)
            ranked = sorted(
                monsters,
                key=lambda monster: (abs(float(monster.get("cr", 0.25)) - target_cr), str(monster.get("name", ""))),
            )
            pool = ranked[: max(1, min(6, len(ranked)))]
            selected = random.choice(pool) if pool else (monsters[0] if monsters else {})

        stats = dict(selected.get("stats", {}))
        ember_stats = {
            "MIG": int(stats.get("str", 10)),
            "AGI": int(stats.get("dex", 10)),
            "END": int(stats.get("con", 10)),
            "MND": int(stats.get("int", 10)),
            "INS": int(stats.get("wis", 10)),
            "PRE": int(stats.get("cha", 10)),
        }
        first_attack = next(iter(selected.get("attacks", [])), {})
        melee_bonus = int(first_attack.get("attack_bonus", 2))
        mig_mod = (ember_stats["MIG"] - 10) // 2
        dex_mod = (ember_stats["AGI"] - 10) // 2
        enemy = Character(
            name=str(selected.get("name", preferred_name or "Hostile Foe")),
            hp=int(selected.get("hp", 10)),
            max_hp=int(selected.get("hp", 10)),
            ac=int(selected.get("armor_class", 10)),
            initiative_bonus=dex_mod,
            stats=ember_stats,
            skills={"melee": melee_bonus - mig_mod},
        )
        setattr(enemy, "monster_id", selected.get("id"))
        setattr(enemy, "role", str(selected.get("type", "monster")))
        setattr(enemy, "loot_table", list(selected.get("loot_table", [])))
        return enemy
