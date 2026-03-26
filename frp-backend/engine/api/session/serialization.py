"""Serialization helpers for GameSession."""
from __future__ import annotations

import copy

from engine.world.entity import EntityType


class SessionSerializationMixin:
    """API serialization methods."""

    def to_dict(self) -> dict:
        self.ensure_consistency()
        player_payload = {
            "name": self.player.name,
            "level": self.player.level,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "spell_points": self.player.spell_points,
            "max_spell_points": self.player.max_spell_points,
            "xp": self.player.xp,
            "classes": self.player.classes,
            "gold": getattr(self.player, "gold", 0),
            "inventory": copy.deepcopy(self.inventory),
            "equipment": {slot: copy.deepcopy(item) for slot, item in self.equipment.items() if item is not None},
            "position": list(self.position),
            "facing": self.facing,
            "conditions": list(self.player.conditions),
            "skill_proficiencies": list(getattr(self.player, "skill_proficiencies", [])),
            "expertise_skills": list(getattr(self.player, "expertise_skills", [])),
            "proficiency_bonus": int(getattr(self.player, "proficiency_bonus", 2)),
            "passives": dict(getattr(self.player, "passives", {})),
            "alignment": getattr(self.player, "alignment", "TN"),
            "alignment_axes": dict(getattr(self.player, "alignment_axes", {})),
            "hit_dice": {
                "size": int(getattr(self.player, "hit_die_size", 8)),
                "total": int(getattr(self.player, "hit_dice_total", 0)),
                "remaining": int(getattr(self.player, "hit_dice_remaining", 0)),
            },
            "exhaustion_level": int(getattr(self.player, "exhaustion_level", 0)),
            "death_saves": {
                "successes": int(getattr(self.player, "death_save_successes", 0)),
                "failures": int(getattr(self.player, "death_save_failures", 0)),
                "stable": bool(getattr(self.player, "is_stable", False)),
            },
            "creation_answers": copy.deepcopy(getattr(self.player, "creation_answers", [])),
            "creation_profile": copy.deepcopy(getattr(self.player, "creation_profile", {})),
        }
        result = {
            "session_id": self.session_id,
            "scene": self.dm_context.scene_type.value,
            "location": self.dm_context.location,
            "player": player_payload,
            "in_combat": self.in_combat(),
            "turn": self.dm_context.turn,
            "position": list(self.position),
            "facing": self.facing,
        }

        if self.ap_tracker:
            result["ap"] = {
                "current": self.ap_tracker.current_ap,
                "max": self.ap_tracker.max_ap,
            }
            result["player"]["ap"] = dict(result["ap"])
        if self.in_combat() and self.combat is not None:
            player_combatant = next(
                (combatant for combatant in self.combat.combatants if combatant.name == self.player.name),
                None,
            )
            if player_combatant is not None:
                combat_ap = {
                    "current": int(player_combatant.ap),
                    "max": 3,
                }
                result["ap"] = combat_ap
                result["player"]["ap"] = dict(combat_ap)

        if self.inventory:
            result["inventory"] = copy.deepcopy(self.inventory)
        if self.equipment:
            equipped = {slot: item for slot, item in self.equipment.items() if item is not None}
            if equipped:
                result["equipment"] = copy.deepcopy(equipped)

        if self.physical_inventory:
            base_encumbrance = self.physical_inventory.encumbrance_ap_penalty(self._get_strength_modifier())
            result["weight"] = {
                "current": round(self.current_carry_weight(), 1),
                "max": round(self.max_carry_weight(), 1),
                "encumbrance_penalty": 999 if base_encumbrance >= 999 else base_encumbrance + self.movement_ap_penalty(),
            }

        if self.game_time:
            result["game_time"] = self.game_time.to_dict()

        if self.entities:
            result["entities"] = [
                {
                    "id": eid,
                    "name": entity.get("name", eid),
                    "type": entity.get("type", "npc"),
                    "position": entity.get("position", [0, 0]),
                    "faction": entity.get("faction", ""),
                    "role": entity.get("role", ""),
                }
                for eid, entity in self.entities.items()
            ]

        ground_items = []
        if self.spatial_index and self.spatial_index.count() > 0:
            spatial_entities = []
            for ent in self.spatial_index.all_entities():
                if ent.id == "player":
                    continue
                spatial_entities.append(ent.to_dict())
            if spatial_entities:
                result["world_entities"] = spatial_entities
                ground_items = [ent for ent in spatial_entities if ent.get("entity_type") == EntityType.ITEM.value]
        result["ground_items"] = ground_items

        if self.map_data:
            result["map"] = {
                "width": self.map_data.width,
                "height": self.map_data.height,
                "spawn_point": list(self.map_data.spawn_point),
            }

        active_quests = []
        if self.quest_tracker:
            active = self.quest_tracker.get_active_quests()
            if active:
                active_quests = [
                    {
                        "quest_id": quest.quest_id,
                        "title": quest.title,
                        "deadline": quest.deadline_hour,
                        "status": quest.status.value,
                    }
                    for quest in active
                ]
        result["active_quests"] = active_quests
        result["quest_offers"] = copy.deepcopy(self.quest_offers) if self.quest_offers else []
        result["campaign_state"] = copy.deepcopy(self.campaign_state) if self.campaign_state else {}
        result["timed_conditions"] = self.timed_condition_payload()
        result["conversation_state"] = copy.deepcopy(self.conversation_state)

        if self.body_tracker:
            injuries = self.body_tracker.get_injury_effects()
            if injuries:
                result["body_status"] = injuries
        if self.narration_context:
            result["narration_context"] = copy.deepcopy(self.narration_context)
        if self.last_save_slot:
            result["last_save_slot"] = self.last_save_slot

        return result
