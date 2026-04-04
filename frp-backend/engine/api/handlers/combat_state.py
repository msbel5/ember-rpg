"""Combat serialization and world-sync helper methods (kernel-native)."""
from __future__ import annotations

from typing import Any, Optional

from engine.api.session.core import GameSession
from engine.kernel.actor_records import ActorRecord
from engine.kernel.combat_engine import CombatState, CombatantEntry, is_combat_over


class CombatStateMixin:
    """Focused helpers for combat state exposure and combat/world synchronization."""

    # ── Primary serializer: kernel CombatState -> Godot-compatible dict ──

    def _combat_state(self, session: GameSession) -> Optional[dict]:
        """Serialize kernel CombatState for the Godot client.

        Reads combat_state and combat_actors from session.campaign_state.
        Returns None when there is no active combat.
        """
        combat: Optional[CombatState] = session.campaign_state.get("combat_state")
        if combat is None:
            return None

        actors: dict[str, ActorRecord] = session.campaign_state.get("combat_actors", {})
        ended = combat.phase == "resolved" or is_combat_over(combat, actors)
        active_entry: Optional[CombatantEntry] = combat.active_combatant if not ended else None
        active_actor: Optional[ActorRecord] = actors.get(active_entry.actor_id) if active_entry else None

        return {
            "round": combat.round_number,
            "phase": "ended" if ended else "active_turn",
            "active": active_actor.name if active_actor else None,
            "turn_actor_id": active_entry.actor_id if active_entry else None,
            "ended": ended,
            "combatants": [
                self._serialize_combatant(entry, actors)
                for entry in combat.combatants
            ],
            "available_actions": [] if ended else ["attack", "defend", "use", "disengage", "flee"],
            "targets": [
                {
                    "name": actors[entry.actor_id].name,
                    "entity_id": entry.actor_id,
                    "hp": actors[entry.actor_id].hp,
                    "max_hp": actors[entry.actor_id].max_hp,
                }
                for entry in combat.combatants
                if (
                    entry.actor_id in actors
                    and active_entry is not None
                    and entry.actor_id != active_entry.actor_id
                    and actors[entry.actor_id].alive
                )
            ],
            "log_entries": [],
        }

    def _serialize_combatant(
        self,
        entry: CombatantEntry,
        actors: dict[str, ActorRecord],
    ) -> dict[str, Any]:
        """Build a single combatant dict for the Godot client."""
        actor = actors.get(entry.actor_id)
        if actor is None:
            # Defensive fallback for missing actor data.
            return {
                "name": entry.actor_id,
                "entity_id": entry.actor_id,
                "hp": 0,
                "max_hp": 0,
                "dead": True,
                "initiative": entry.initiative,
                "conditions": [],
                "turn_resources": self._serialize_turn_resources(entry),
                "death_saves": {"successes": 0, "failures": 0},
                "stable": False,
            }

        return {
            "name": actor.name,
            "entity_id": entry.actor_id,
            "hp": actor.hp,
            "max_hp": actor.max_hp,
            "dead": not actor.alive,
            "initiative": entry.initiative,
            "conditions": [c.name for c in actor.conditions],
            "turn_resources": self._serialize_turn_resources(entry),
            "death_saves": {
                "successes": int(actor.raw_payload.get("death_save_successes", 0)),
                "failures": int(actor.raw_payload.get("death_save_failures", 0)),
            },
            "stable": bool(actor.raw_payload.get("is_stable", False)),
        }

    @staticmethod
    def _serialize_turn_resources(entry: CombatantEntry) -> dict[str, Any]:
        """Map kernel TurnResources to the legacy client format."""
        tr = entry.turn_resources
        return {
            "action_available": tr.action,
            "bonus_action_available": tr.bonus_action,
            "reaction_available": tr.reaction,
            "movement_remaining": tr.movement,
            "speed": tr.max_movement,
            "disengaged_until_turn_end": False,
        }

    # ── Index / ID helpers ───────────────────────────────────────────────

    def _combat_player_index(self, combat: CombatState, player_id: str) -> Optional[int]:
        """Return the index of the player entry in the combat order."""
        return next(
            (i for i, entry in enumerate(combat.combatants) if entry.actor_id == player_id),
            None,
        )

    def _combat_entity_id(self, entry: CombatantEntry) -> str:
        """Return the actor_id for a combatant entry."""
        return entry.actor_id

    # ── World-state synchronization ──────────────────────────────────────

    def _sync_combatant_world_state(self, session: GameSession, entry: CombatantEntry) -> None:
        """Push kernel ActorRecord HP/alive back into session.entities."""
        actors: dict[str, ActorRecord] = session.campaign_state.get("combat_actors", {})
        actor = actors.get(entry.actor_id)
        if actor is None:
            return
        entity_id = entry.actor_id
        if entity_id in session.entities:
            session.entities[entity_id]["hp"] = actor.hp
            session.entities[entity_id]["alive"] = actor.alive
            session.entities[entity_id]["blocking"] = actor.alive
            entity_ref = session.entities[entity_id].get("entity_ref")
            if entity_ref is not None:
                entity_ref.hp = actor.hp
                entity_ref.alive = actor.alive
                entity_ref.blocking = actor.alive
                session.sync_entity_record(entity_id, entity_ref)

    def _sync_all_combat_world_state(self, session: GameSession) -> None:
        """Sync all combatants back to the world entity table."""
        combat: Optional[CombatState] = session.campaign_state.get("combat_state")
        if combat is None:
            return
        for entry in combat.combatants:
            self._sync_combatant_world_state(session, entry)

    # ── Auto-advance enemy turns ─────────────────────────────────────────

    def _advance_combat_until_player_turn(self, session: GameSession) -> list[str]:
        """Skip enemy turns with simple AI until the player's turn arrives."""
        messages: list[str] = []
        combat: Optional[CombatState] = session.campaign_state.get("combat_state")
        if combat is None:
            return messages

        actors: dict[str, ActorRecord] = session.campaign_state.get("combat_actors", {})

        # Find the player entry id.
        player_id: Optional[str] = None
        for entry in combat.combatants:
            if entry.is_player:
                player_id = entry.actor_id
                break
        if player_id is None:
            return messages

        from engine.kernel.combat_engine import end_turn, execute_attack

        max_iterations = len(combat.combatants) * 2
        for _ in range(max_iterations):
            if combat.phase == "resolved" or is_combat_over(combat, actors):
                break
            active = combat.active_combatant
            if active.actor_id == player_id:
                break
            active_actor = actors.get(active.actor_id)
            if active_actor is None or not active_actor.alive:
                end_turn(combat)
                continue
            # Simple enemy AI: attack the player.
            player_actor = actors.get(player_id)
            if player_actor is not None and player_actor.alive:
                try:
                    result = execute_attack(combat, actors, active.actor_id, player_id)
                    hit = result.combat_result.hit
                    sr = result.combat_result.strike_resolution
                    damage = sr.effective_damage if sr else 0
                    messages.append(
                        self._build_enemy_combat_narrative(session, active_actor, hit, damage)
                    )
                except (ValueError, KeyError):
                    pass
            end_turn(combat)

        self._sync_all_combat_world_state(session)
        return messages

    # ── Positional helpers ───────────────────────────────────────────────

    def _combatant_position(self, session: GameSession, entry: CombatantEntry) -> tuple[int, int]:
        """Get the world position of a combatant."""
        entity_id = entry.actor_id
        if entity_id in session.entities:
            position = session.entities[entity_id].get("position", list(session.position))
            return (position[0], position[1])
        return tuple(session.position)

    def _opportunity_attack_messages(
        self,
        session: GameSession,
        old_pos: tuple[int, int],
        new_pos: tuple[int, int],
    ) -> list[str]:
        """Check for opportunity attacks when the player moves."""
        combat: Optional[CombatState] = session.campaign_state.get("combat_state")
        if combat is None:
            return []
        actors: dict[str, ActorRecord] = session.campaign_state.get("combat_actors", {})

        # Find the player entry.
        player_id: Optional[str] = None
        for entry in combat.combatants:
            if entry.is_player:
                player_id = entry.actor_id
                break
        if player_id is None:
            return []

        from engine.kernel.combat_engine import execute_attack

        messages: list[str] = []
        for entry in combat.combatants:
            entry_actor = actors.get(entry.actor_id)
            if entry.actor_id == player_id or entry_actor is None or not entry_actor.alive:
                continue
            if not entry.turn_resources.reaction:
                continue
            active = combat.active_combatant
            # Skip if active combatant has disengaged (tracked in raw_payload).
            active_actor = actors.get(active.actor_id)
            if active_actor and active_actor.raw_payload.get("disengaged_until_turn_end", False):
                continue
            cpos = self._combatant_position(session, entry)
            old_adj = max(abs(old_pos[0] - cpos[0]), abs(old_pos[1] - cpos[1])) <= 1
            new_adj = max(abs(new_pos[0] - cpos[0]), abs(new_pos[1] - cpos[1])) <= 1
            if old_adj and not new_adj:
                entry.turn_resources.reaction = False
                attacker_actor = actors.get(entry.actor_id)
                # Temporarily swap to this combatant's turn for the attack.
                saved_turn = combat.current_turn_index
                combat.current_turn_index = combat.combatants.index(entry)
                try:
                    result = execute_attack(combat, actors, entry.actor_id, player_id)
                    if result.combat_result.hit:
                        messages.append(
                            f"{attacker_actor.name} lashes out with an opportunity attack "
                            f"for {result.combat_result.damage} damage."
                        )
                    else:
                        messages.append(
                            f"{attacker_actor.name} swings as you withdraw, but misses."
                        )
                except (ValueError, KeyError):
                    pass
                combat.current_turn_index = saved_turn

        self._sync_all_combat_world_state(session)
        return messages

    # ── World-entity -> ActorRecord factory ──────────────────────────────

    def _character_from_world_entity(
        self, entity_id: str, entity: dict[str, Any]
    ) -> Optional[ActorRecord]:
        """Build a kernel ActorRecord from a world entity dict.

        Used when spawning NPCs into combat from the session.entities table.
        """
        from engine.kernel.actor_foundation import ActorIdentity, ActorPosition

        entity_ref = entity.get("entity_ref")
        role = entity.get("role") or entity.get("job") or getattr(entity_ref, "job", None)
        if not role and entity.get("type") != "npc":
            return None

        stat_presets: dict[str, dict[str, int]] = {
            "guard": {"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 11},
            "merchant": {"MIG": 8, "AGI": 10, "END": 10, "MND": 10, "INS": 12, "PRE": 13},
            "blacksmith": {"MIG": 14, "AGI": 10, "END": 12, "MND": 9, "INS": 11, "PRE": 10},
            "innkeeper": {"MIG": 10, "AGI": 9, "END": 11, "MND": 10, "INS": 12, "PRE": 12},
            "quest_giver": {"MIG": 9, "AGI": 9, "END": 10, "MND": 12, "INS": 12, "PRE": 13},
            "spy": {"MIG": 9, "AGI": 13, "END": 9, "MND": 11, "INS": 13, "PRE": 11},
        }
        hp = int(getattr(entity_ref, "hp", entity.get("hp", 10)))
        max_hp = int(getattr(entity_ref, "max_hp", entity.get("max_hp", hp)))
        base_stats = stat_presets.get(role, {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
        full_stats: dict[str, int | float] = dict(base_stats)
        full_stats["hp"] = hp
        full_stats["max_hp"] = max_hp

        return ActorRecord(
            identity=ActorIdentity(
                actor_id=entity_id,
                display_name=entity.get("name", entity_id),
                actor_type="npc",
            ),
            position=ActorPosition(x=0, y=0),
            action_points=6,
            max_action_points=6,
            alive=hp > 0,
            stats=full_stats,
            raw_payload={
                "role": role or "npc",
                "weapon_material": "iron" if role in {"guard", "blacksmith"} else "wood",
                "equipped_armor": ["shield"] if role == "guard" else [],
            },
        )

    # ── Weapon ItemStack builder ─────────────────────────────────────────

    def _build_weapon_item(self, item_data: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Build a weapon payload dict from raw item data.

        Returns a plain dict suitable for kernel ItemStack construction
        rather than the legacy Item class.
        """
        if not item_data:
            return None
        damage = max(1, int(item_data.get("damage", 4)))
        damage_dice = item_data.get("damage_dice") or f"1d{damage}"
        return {
            "id": item_data.get("id"),
            "name": item_data.get("name", "Weapon"),
            "value": int(item_data.get("value", 0)),
            "weight": float(item_data.get("weight", 0.0)),
            "item_type": "weapon",
            "damage_dice": damage_dice,
            "damage_type": item_data.get("damage_type", "slashing"),
            "ac_bonus": int(item_data.get("ac_bonus", 0)),
        }

    # ── Target finder ────────────────────────────────────────────────────

    def _find_target(
        self,
        combat: CombatState,
        target_name: Optional[str],
        exclude: str,
    ) -> Optional[int]:
        """Find a target combatant index by name, excluding the given actor.

        The exclude parameter is an actor_id.
        """
        actors: dict[str, ActorRecord] = {}
        # Attempt to read actors from wherever the mixin has access.
        # Callers should ensure combat_actors is in campaign_state.
        if hasattr(self, "_current_session"):
            actors = getattr(self._current_session, "campaign_state", {}).get("combat_actors", {})

        if target_name:
            for index, entry in enumerate(combat.combatants):
                actor = actors.get(entry.actor_id)
                name = actor.name if actor else entry.actor_id
                if (
                    target_name.lower() in name.lower()
                    and entry.actor_id != exclude
                    and (actor is None or actor.alive)
                ):
                    return index

        for index, entry in enumerate(combat.combatants):
            actor = actors.get(entry.actor_id)
            if entry.actor_id != exclude and (actor is None or actor.alive):
                return index
        return None
