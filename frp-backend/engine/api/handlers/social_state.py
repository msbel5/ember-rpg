"""Social state helpers for conversation memory and attitude tracking."""
from __future__ import annotations

from typing import Optional

from engine.api.game_session import GameSession
from engine.world.proximity import get_interaction_range

from engine.api.runtime_constants import DEFAULT_NPC_ATTITUDE, INTERACTION_HOLD_TURNS, SOCIAL_ATTITUDE_DCS


class SocialStateMixin:
    """Focused helpers for social state, attitude, and memory propagation."""

    def _hold_interaction_target(self, session: GameSession, entity_id: Optional[str], action_name: str) -> None:
        if not entity_id:
            return
        session.hold_entity_position(entity_id, turns=INTERACTION_HOLD_TURNS.get(action_name, 1))

    def _entity_attitude(self, entity: dict) -> str:
        return str(entity.get("attitude") or DEFAULT_NPC_ATTITUDE.get(entity.get("role", ""), "indifferent")).lower()

    def _set_entity_attitude(self, session: GameSession, entity_id: str, attitude: str) -> None:
        if entity_id in session.entities:
            session.entities[entity_id]["attitude"] = attitude
            entity_ref = session.entities[entity_id].get("entity_ref")
            if entity_ref is not None:
                entity_ref.attitude = attitude
                if attitude == "hostile":
                    entity_ref.disposition = "hostile"
                elif attitude == "friendly":
                    entity_ref.disposition = "friendly"
                else:
                    entity_ref.disposition = "neutral"
                session.sync_entity_record(entity_id, entity_ref)

    def _social_dc(self, entity: dict, severity: str = "minor_risk") -> int:
        attitude = self._entity_attitude(entity)
        return SOCIAL_ATTITUDE_DCS.get(attitude, SOCIAL_ATTITUDE_DCS["indifferent"]).get(severity, 15)

    def _shift_attitude_step(self, session: GameSession, entity_id: str, delta: int) -> str:
        steps = ["hostile", "indifferent", "friendly"]
        current = self._entity_attitude(session.entities.get(entity_id, {}))
        idx = steps.index(current) if current in steps else 1
        new_idx = max(0, min(len(steps) - 1, idx + delta))
        new_attitude = steps[new_idx]
        self._set_entity_attitude(session, entity_id, new_attitude)
        return new_attitude

    def _conversation_target_entity(self, session: GameSession) -> Optional[tuple[str, dict]]:
        npc_id = session.conversation_state.get("npc_id")
        if npc_id and npc_id in session.entities:
            return (npc_id, session.entities[npc_id])
        npc_name = session.conversation_state.get("npc_name")
        if npc_name:
            return self._find_entity_by_name(session, npc_name)
        return None

    def _clear_conversation_if_invalid(self, session: GameSession) -> None:
        if session.in_combat():
            session.clear_conversation_target()
            return
        target = self._conversation_target_entity(session)
        if target is None:
            session.clear_conversation_target()
            return
        entity_id, entity = target
        if not entity.get("alive", True):
            session.clear_conversation_target()
            return
        pos = self._live_entity_position(session, entity_id, entity.get("position", [0, 0]))
        if max(abs(session.position[0] - pos[0]), abs(session.position[1] - pos[1])) > get_interaction_range("social"):
            session.clear_conversation_target()

    def _record_eavesdroppers(self, session: GameSession, speaker_entity_id: Optional[str], transcript: str) -> None:
        for entity_id, entity in session.entities.items():
            if entity_id == speaker_entity_id or entity_id == "player":
                continue
            if not entity.get("alive", True):
                continue
            ent_pos = entity.get("position", [0, 0])
            dist = max(abs(session.position[0] - ent_pos[0]), abs(session.position[1] - ent_pos[1]))
            if dist <= 2:
                memory_time = session.game_time.to_string() if session.game_time else "Day 1, 08:00 (morning)"
                session.npc_memory.record_interaction(
                    entity_id,
                    f"[Overheard] {transcript}",
                    "neutral",
                    memory_time,
                    facts=[f"Overheard conversation near {speaker_entity_id}"],
                )

    def _apply_alignment_shift(self, session: GameSession, law_delta: int = 0, good_delta: int = 0) -> None:
        axes = getattr(session.player, "alignment_axes", None)
        if axes is None:
            return
        axes["law_chaos"] = max(-100, min(100, axes.get("law_chaos", 0) + law_delta))
        axes["good_evil"] = max(-100, min(100, axes.get("good_evil", 0) + good_delta))
        session.player.set_alignment_from_axes()
