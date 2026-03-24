"""
Ember RPG - API Layer
GameSession: per-player game state container
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid

from engine.core.character import Character
from engine.core.dm_agent import DMContext, SceneType
from engine.core.combat import CombatManager
from engine.world import WorldState
from engine.npc.npc_memory import NPCMemoryManager
from engine.world.consequence import CascadeEngine


@dataclass
class GameSession:
    """
    Holds all state for one player's game session.

    Attributes:
        session_id: Unique session identifier (UUID)
        player: Player character
        dm_context: DM context (scene, location, history)
        combat: Active CombatManager (None if not in combat)
        created_at: Session creation timestamp
        last_action: Timestamp of last player action
    """
    player: Character
    dm_context: DMContext
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    combat: Optional[CombatManager] = None
    world_state: Optional[WorldState] = None
    npc_memory: Optional[NPCMemoryManager] = None
    cascade_engine: Optional[CascadeEngine] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_action: datetime = field(default_factory=datetime.now)
    position: list = field(default_factory=lambda: [0, 0])
    facing: str = "north"

    def __post_init__(self):
        if self.world_state is None:
            self.world_state = WorldState(game_id=self.session_id)
        if self.npc_memory is None:
            self.npc_memory = NPCMemoryManager(session_id=self.session_id)
        if self.cascade_engine is None:
            self.cascade_engine = CascadeEngine()

    def touch(self):
        """Update last_action timestamp."""
        self.last_action = datetime.now()

    def in_combat(self) -> bool:
        """Return True if session has active combat."""
        return self.combat is not None and not self.combat.combat_ended

    def to_dict(self) -> dict:
        """Serialize session state for API responses."""
        return {
            "session_id": self.session_id,
            "scene": self.dm_context.scene_type.value,
            "location": self.dm_context.location,
            "player": {
                "name": self.player.name,
                "level": self.player.level,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "spell_points": self.player.spell_points,
                "max_spell_points": self.player.max_spell_points,
                "xp": self.player.xp,
                "classes": self.player.classes,
            },
            "in_combat": self.in_combat(),
            "turn": self.dm_context.turn,
            "position": list(self.position),
            "facing": self.facing,
        }
