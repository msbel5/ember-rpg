"""Combat serialization helpers."""
from __future__ import annotations

from typing import Any, Dict, Optional


class SaveCombatStateMixin:
    """Combat serialization and deserialization."""

    @staticmethod
    def _serialize_combat(combat) -> Optional[Dict[str, Any]]:
        if combat is None:
            return None
        return {
            "current_turn": combat.current_turn,
            "round": combat.round,
            "combat_ended": combat.combat_ended,
            "log": list(combat.log),
            "combatants": [
                {
                    "character": {
                        **combatant.character.to_dict(),
                        **(
                            {"_entity_id": getattr(combatant.character, "_entity_id")}
                            if hasattr(combatant.character, "_entity_id")
                            else {}
                        ),
                        **(
                            {"role": getattr(combatant.character, "role")}
                            if hasattr(combatant.character, "role")
                            else {}
                        ),
                        **(
                            {"equipped_armor": list(getattr(combatant.character, "equipped_armor", []))}
                            if hasattr(combatant.character, "equipped_armor")
                            else {}
                        ),
                        **(
                            {"weapon_material": getattr(combatant.character, "weapon_material")}
                            if hasattr(combatant.character, "weapon_material")
                            else {}
                        ),
                    },
                    "initiative": combatant.initiative,
                    "ap": combatant.ap,
                    "conditions": [condition.__dict__ for condition in combatant.conditions],
                    "is_dead": combatant.is_dead,
                    "action_available": bool(getattr(combatant, "action_available", True)),
                    "bonus_action_available": bool(getattr(combatant, "bonus_action_available", True)),
                    "reaction_available": bool(getattr(combatant, "reaction_available", True)),
                    "movement_remaining": int(getattr(combatant, "movement_remaining", 0)),
                    "speed": int(getattr(combatant, "speed", 0)),
                    "disengaged_until_turn_end": bool(getattr(combatant, "disengaged_until_turn_end", False)),
                }
                for combatant in combat.combatants
            ],
        }

    @staticmethod
    def _deserialize_combat(data: Optional[Dict[str, Any]], player):
        if not data:
            return None
        from engine.core.character import Character
        from engine.core.combat import CombatManager, Combatant, Condition

        combat = object.__new__(CombatManager)
        combat.combatants = []
        for combatant_data in data.get("combatants", []):
            char_data = dict(combatant_data.get("character", {}))
            entity_id = char_data.pop("_entity_id", None)
            role = char_data.pop("role", None)
            equipped_armor = list(char_data.pop("equipped_armor", []) or [])
            weapon_material = char_data.pop("weapon_material", None)
            character = player if char_data.get("name") == getattr(player, "name", None) else Character.from_dict(char_data)
            if entity_id is not None:
                character._entity_id = entity_id
            if role is not None:
                character.role = role
            if equipped_armor is not None:
                character.equipped_armor = equipped_armor
            if weapon_material is not None:
                character.weapon_material = weapon_material
            combat.combatants.append(
                Combatant(
                    character=character,
                    initiative=combatant_data.get("initiative", 0),
                    ap=combatant_data.get("ap", 3),
                    conditions=[Condition(**condition) for condition in combatant_data.get("conditions", [])],
                    is_dead=combatant_data.get("is_dead", False),
                )
            )
            combat.combatants[-1].action_available = bool(combatant_data.get("action_available", True))
            combat.combatants[-1].bonus_action_available = bool(combatant_data.get("bonus_action_available", True))
            combat.combatants[-1].reaction_available = bool(combatant_data.get("reaction_available", True))
            combat.combatants[-1].movement_remaining = int(combatant_data.get("movement_remaining", 0))
            combat.combatants[-1].speed = int(combatant_data.get("speed", combat.combatants[-1].speed))
            combat.combatants[-1].disengaged_until_turn_end = bool(combatant_data.get("disengaged_until_turn_end", False))
        combat.current_turn = data.get("current_turn", 0)
        combat.round = data.get("round", 1)
        combat.log = list(data.get("log", []))
        combat.combat_ended = data.get("combat_ended", False)
        import random

        combat.rng = random.Random()
        return combat
