"""Conversation and session replacement helpers for GameSession."""
from __future__ import annotations

from typing import Optional

from engine.api.session_utils import make_conversation_state


class SessionConversationMixin:
    """Conversation-state methods."""

    def replace_with(self, other: "GameSession", preserve_session_id: bool = False) -> None:
        current_session_id = self.session_id
        for field_name in self.__dataclass_fields__:
            setattr(self, field_name, getattr(other, field_name))
        if preserve_session_id:
            self.session_id = current_session_id
        self.ensure_consistency()

    def set_conversation_target(
        self,
        target_type: str,
        *,
        npc_id: Optional[str] = None,
        npc_name: Optional[str] = None,
    ) -> None:
        self.conversation_state = make_conversation_state(
            self.dm_context.turn if self.dm_context is not None else 0,
            target_type=target_type,
            npc_id=npc_id,
            npc_name=npc_name,
        )

    def clear_conversation_target(self) -> None:
        self.conversation_state = make_conversation_state(
            self.dm_context.turn if self.dm_context is not None else 0,
        )
