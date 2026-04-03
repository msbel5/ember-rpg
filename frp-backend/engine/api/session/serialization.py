"""Serialization helpers for GameSession.

Kernel-native: player is always an ActorRecord — no getattr defensive
reads needed.  All properties are defined on ActorRecord with proper
data-driven fallbacks.
"""
from __future__ import annotations

import copy
import logging

from engine.world.entity import EntityType

log = logging.getLogger(__name__)


class SessionSerializationMixin:
    """API serialization methods."""

    def _combat_payload(self) -> dict | None:
        kernel_state = self.campaign_state.get("combat_state") if isinstance(self.campaign_state, dict) else None
        if kernel_state is not None:
            actors = self.campaign_state.get("combat_actors", {})
            active_entry = (
                kernel_state.active_combatant
                if getattr(kernel_state, "combatants", None) and str(getattr(kernel_state, "phase", "active")) != "resolved"
                else None
            )
            active_actor = actors.get(active_entry.actor_id) if active_entry is not None else None
            return {
                "round": int(getattr(kernel_state, "round_number", 1)),
                "phase": str(getattr(kernel_state, "phase", "active")),
                "active": getattr(active_actor, "name", None),
                "turn_actor_id": getattr(active_entry, "actor_id", None),
                "ended": str(getattr(kernel_state, "phase", "active")) == "resolved",
                "combatants": [
                    {
                        "name": getattr(actor, "name", entry.actor_id),
                        "entity_id": entry.actor_id,
                        "hp": int(getattr(actor, "hp", actor.stats.get("hp", 0) if actor is not None else 0)),
                        "max_hp": int(getattr(actor, "max_hp", actor.stats.get("max_hp", 0) if actor is not None else 0)),
                        "ap": int(getattr(entry.turn_resources, "movement", 0)),
                        "dead": not bool(getattr(actor, "alive", False)),
                        "initiative": int(getattr(entry, "initiative", 0)),
                        "conditions": list(getattr(actor, "condition_names", [])) if actor is not None else [],
                        "resources": {
                            "action_available": bool(getattr(entry.turn_resources, "action", False)),
                            "bonus_action_available": bool(getattr(entry.turn_resources, "bonus_action", False)),
                            "reaction_available": bool(getattr(entry.turn_resources, "reaction", False)),
                            "movement_remaining": int(getattr(entry.turn_resources, "movement", 0)),
                            "speed": int(getattr(entry.turn_resources, "max_movement", 0)),
                            "disengaged_until_turn_end": bool(
                                getattr(actor, "raw_payload", {}).get("disengaged_until_turn_end", False)
                            ) if actor is not None else False,
                        },
                        "death_saves": {
                            "successes": int(getattr(actor, "death_save_successes", 0)) if actor is not None else 0,
                            "failures": int(getattr(actor, "death_save_failures", 0)) if actor is not None else 0,
                        },
                        "stable": bool(getattr(actor, "is_stable", False)) if actor is not None else False,
                    }
                    for entry in getattr(kernel_state, "combatants", [])
                    for actor in [actors.get(entry.actor_id)]
                ],
                "available_actions": []
                if str(getattr(kernel_state, "phase", "active")) == "resolved"
                else ["attack", "defend", "use", "disengage", "flee"],
                "targets": [
                    {
                        "name": getattr(actor, "name", entry.actor_id),
                        "entity_id": entry.actor_id,
                        "hp": int(getattr(actor, "hp", actor.stats.get("hp", 0) if actor is not None else 0)),
                        "max_hp": int(getattr(actor, "max_hp", actor.stats.get("max_hp", 0) if actor is not None else 0)),
                    }
                    for entry in getattr(kernel_state, "combatants", [])
                    for actor in [actors.get(entry.actor_id)]
                    if active_entry is not None
                    and entry.actor_id != active_entry.actor_id
                    and actor is not None
                    and bool(getattr(actor, "alive", False))
                ],
                "log_entries": list(self.campaign_state.get("combat_log", [])),
            }
        if not self.in_combat() or self.combat is None:
            return None
        active_combatant = self.combat.active_combatant if not self.combat.combat_ended else None
        return {
            "round": self.combat.round,
            "phase": "ended" if self.combat.combat_ended else "active_turn",
            "active": active_combatant.name if active_combatant is not None else None,
            "turn_actor_id": getattr(getattr(active_combatant, "character", None), "_entity_id", None) if active_combatant is not None else None,
            "ended": self.combat.combat_ended,
            "combatants": [
                {
                    "name": combatant.name,
                    "entity_id": getattr(combatant.character, "_entity_id", None),
                    "hp": combatant.character.hp,
                    "max_hp": combatant.character.max_hp,
                    "ap": combatant.ap,
                    "dead": combatant.is_dead,
                    "initiative": combatant.initiative,
                    "conditions": [
                        c.name if hasattr(c, "name") else str(c)
                        for c in getattr(combatant.character, "conditions", [])
                    ],
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
                for combatant in self.combat.combatants
            ],
            "available_actions": [] if self.combat.combat_ended else ["attack", "defend", "use", "disengage", "flee"],
            "targets": [
                {
                    "name": combatant.name,
                    "entity_id": getattr(combatant.character, "_entity_id", None),
                    "hp": combatant.character.hp,
                    "max_hp": combatant.character.max_hp,
                }
                for combatant in self.combat.combatants
                if active_combatant is not None and combatant.name != active_combatant.name and not combatant.is_dead
            ],
            "log_entries": [],
        }

    def to_dict(self) -> dict:
        self.ensure_consistency()
        # All reads go directly through ActorRecord typed properties
        # — no getattr defense needed, kernel guarantees the API
        player_payload = {
            "name": self.player.name,
            "level": self.player.level,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "spell_points": self.player.spell_points,
            "max_spell_points": self.player.max_spell_points,
            "xp": self.player.xp,
            "classes": self.player.classes,
            "stats": copy.deepcopy(self.player.stats),
            "skills": copy.deepcopy(self.player.skills),
            "ac": self.player.ac,
            "initiative_bonus": self.player.initiative_bonus,
            "gold": self.player.gold,
            "inventory": copy.deepcopy(self.inventory),
            "equipment": {slot: copy.deepcopy(item) for slot, item in self.equipment.items() if item is not None},
            "position": list(self.position),
            "facing": self.facing,
            "conditions": [c.name for c in self.player.conditions],
            "skill_proficiencies": list(self.player.skill_proficiencies),
            "expertise_skills": list(self.player.expertise_skills),
            "proficiency_bonus": self.player.proficiency_bonus,
            "passives": dict(self.player.passives),
            "alignment": self.player.alignment,
            "alignment_axes": dict(self.player.alignment_axes),
            "hit_dice": {
                "size": self.player.hit_die_size,
                "total": self.player.hit_dice_total,
                "remaining": self.player.hit_dice_remaining,
            },
            "exhaustion_level": self.player.exhaustion_level,
            "death_saves": {
                "successes": self.player.death_save_successes,
                "failures": self.player.death_save_failures,
                "stable": self.player.is_stable,
            },
            "creation_answers": copy.deepcopy(self.player.creation_answers),
            "creation_profile": copy.deepcopy(self.player.creation_profile),
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
            "combat": self._combat_payload(),
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
            base_encumbrance = self.physical_inventory.encumbrance_ap_penalty(self._get_mig_modifier())
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
