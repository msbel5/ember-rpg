"""Combat serialization and world-sync helper methods."""
from __future__ import annotations

from typing import Any, Optional

from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.item import Item, ItemType


class CombatStateMixin:
    """Focused helpers for combat state exposure and combat/world synchronization."""

    def _combat_state(self, combat: Optional[CombatManager]) -> Optional[dict]:
        if combat is None:
            return None
        return {
            "round": combat.round,
            "active": combat.active_combatant.name if not combat.combat_ended else None,
            "ended": combat.combat_ended,
            "combatants": [
                {
                    "name": combatant.name,
                    "hp": combatant.character.hp,
                    "max_hp": combatant.character.max_hp,
                    "ap": combatant.ap,
                    "dead": combatant.is_dead,
                    "initiative": combatant.initiative,
                    "conditions": list(getattr(combatant.character, "conditions", [])),
                    "resources": {
                        "action_available": bool(getattr(combatant, "action_available", True)),
                        "bonus_action_available": bool(getattr(combatant, "bonus_action_available", True)),
                        "reaction_available": bool(getattr(combatant, "reaction_available", True)),
                        "movement_remaining": int(getattr(combatant, "movement_remaining", 0)),
                        "speed": int(getattr(combatant, "speed", 0)),
                        "disengaged_until_turn_end": bool(getattr(combatant, "disengaged_until_turn_end", False)),
                    },
                    "death_saves": {
                        "successes": int(getattr(combatant.character, "death_save_successes", 0)),
                        "failures": int(getattr(combatant.character, "death_save_failures", 0)),
                    },
                    "stable": bool(getattr(combatant.character, "is_stable", False)),
                }
                for combatant in combat.combatants
            ],
        }

    def _combat_player_index(self, combat: CombatManager, player_name: str) -> Optional[int]:
        return next((index for index, combatant in enumerate(combat.combatants) if combatant.name == player_name), None)

    def _combat_entity_id(self, combatant) -> Optional[str]:
        return getattr(combatant.character, "_entity_id", None)

    def _sync_combatant_world_state(self, session: GameSession, combatant) -> None:
        entity_id = self._combat_entity_id(combatant)
        if entity_id and entity_id in session.entities:
            session.entities[entity_id]["hp"] = combatant.character.hp
            session.entities[entity_id]["alive"] = not combatant.is_dead
            session.entities[entity_id]["blocking"] = not combatant.is_dead
            entity_ref = session.entities[entity_id].get("entity_ref")
            if entity_ref is not None:
                entity_ref.hp = combatant.character.hp
                entity_ref.alive = not combatant.is_dead
                entity_ref.blocking = not combatant.is_dead
                session.sync_entity_record(entity_id, entity_ref)

    def _sync_all_combat_world_state(self, session: GameSession, combat: Optional[CombatManager]) -> None:
        if combat is None:
            return
        for combatant in combat.combatants:
            self._sync_combatant_world_state(session, combatant)

    def _advance_combat_until_player_turn(self, session: GameSession) -> list[str]:
        messages: list[str] = []
        if session.combat is None:
            return messages
        combat = session.combat
        max_iterations = len(combat.combatants) * 2
        for _ in range(max_iterations):
            if combat.combat_ended or combat.active_combatant.name == session.player.name:
                break
            active = combat.active_combatant
            if active.is_dead:
                combat.end_turn()
                continue
            player_idx = self._combat_player_index(combat, session.player.name)
            if player_idx is not None:
                result = combat.attack(player_idx)
                messages.append(self._build_enemy_combat_narrative(session, active.character, result.get("hit", False), result.get("damage", 0)))
            combat.end_turn()
        self._sync_all_combat_world_state(session, combat)
        return messages

    def _combatant_position(self, session: GameSession, combatant) -> tuple[int, int]:
        entity_id = self._combat_entity_id(combatant)
        if entity_id and entity_id in session.entities:
            position = session.entities[entity_id].get("position", list(session.position))
            return (position[0], position[1])
        return tuple(session.position)

    def _opportunity_attack_messages(self, session: GameSession, old_pos: tuple[int, int], new_pos: tuple[int, int]) -> list[str]:
        if not session.combat:
            return []
        combat = session.combat
        player_idx = self._combat_player_index(combat, session.player.name)
        if player_idx is None:
            return []
        messages: list[str] = []
        for combatant in combat.combatants:
            if combatant.name == session.player.name or combatant.is_dead:
                continue
            if not getattr(combatant, "reaction_available", True):
                continue
            if getattr(combat.active_combatant, "disengaged_until_turn_end", False):
                continue
            cpos = self._combatant_position(session, combatant)
            old_adj = max(abs(old_pos[0] - cpos[0]), abs(old_pos[1] - cpos[1])) <= 1
            new_adj = max(abs(new_pos[0] - cpos[0]), abs(new_pos[1] - cpos[1])) <= 1
            if old_adj and not new_adj:
                combatant.reaction_available = False
                saved_turn = combat.current_turn
                combat.current_turn = combat.combatants.index(combatant)
                result = combat.attack(player_idx)
                combat.current_turn = saved_turn
                if result.get("hit"):
                    messages.append(f"{combatant.name} lashes out with an opportunity attack for {result.get('damage', 0)} damage.")
                else:
                    messages.append(f"{combatant.name} swings as you withdraw, but misses.")
        self._sync_all_combat_world_state(session, combat)
        return messages

    def _character_from_world_entity(self, entity_id: str, entity: dict[str, Any]) -> Optional[Character]:
        entity_ref = entity.get("entity_ref")
        role = entity.get("role") or entity.get("job") or getattr(entity_ref, "job", None)
        if not role and entity.get("type") != "npc":
            return None

        stat_presets = {
            "guard": {"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 11},
            "merchant": {"MIG": 8, "AGI": 10, "END": 10, "MND": 10, "INS": 12, "PRE": 13},
            "blacksmith": {"MIG": 14, "AGI": 10, "END": 12, "MND": 9, "INS": 11, "PRE": 10},
            "innkeeper": {"MIG": 10, "AGI": 9, "END": 11, "MND": 10, "INS": 12, "PRE": 12},
            "quest_giver": {"MIG": 9, "AGI": 9, "END": 10, "MND": 12, "INS": 12, "PRE": 13},
            "spy": {"MIG": 9, "AGI": 13, "END": 9, "MND": 11, "INS": 13, "PRE": 11},
        }
        hp = int(getattr(entity_ref, "hp", entity.get("hp", 10)))
        max_hp = int(getattr(entity_ref, "max_hp", entity.get("max_hp", hp)))
        character = Character(
            name=entity.get("name", entity_id),
            hp=hp,
            max_hp=max_hp,
            stats=stat_presets.get(role, {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10}),
        )
        character.role = role or "npc"
        character._entity_id = entity_id
        character.equipped_armor = ["shield"] if role == "guard" else []
        character.weapon_material = "iron" if role in {"guard", "blacksmith"} else "wood"
        return character

    def _build_weapon_item(self, item_data: Optional[dict[str, Any]]) -> Optional[Item]:
        if not item_data:
            return None
        damage = max(1, int(item_data.get("damage", 4)))
        damage_dice = item_data.get("damage_dice") or f"1d{damage}"
        return Item(
            id=item_data.get("id"),
            name=item_data.get("name", "Weapon"),
            value=int(item_data.get("value", 0)),
            weight=float(item_data.get("weight", 0.0)),
            item_type=ItemType.WEAPON,
            damage_dice=damage_dice,
            damage_type=item_data.get("damage_type", "slashing"),
            armor_bonus=int(item_data.get("ac_bonus", 0)),
        )

    def _find_target(self, combat: CombatManager, target_name: Optional[str], exclude: str) -> Optional[int]:
        if target_name:
            for index, combatant in enumerate(combat.combatants):
                if target_name.lower() in combatant.name.lower() and not combatant.is_dead and combatant.name != exclude:
                    return index
        for index, combatant in enumerate(combat.combatants):
            if combatant.name != exclude and not combatant.is_dead:
                return index
        return None
