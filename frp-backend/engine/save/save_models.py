"""
Ember RPG — Save/Load Data Models

Schema v4.0: Kernel-pure save format. All state is kernel-native
(ActorRecord, GameState, WorldState, CombatState). No legacy Character
or CombatManager objects in the save payload.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


CURRENT_SCHEMA_VERSION = "4.0"


def validate_schema_version(data: dict) -> None:
    """Raise ValueError if the save uses an unsupported schema version."""
    version = str(data.get("schema_version", ""))
    if version != CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported save schema version '{version}'. "
            f"Expected '{CURRENT_SCHEMA_VERSION}'. "
            f"Old saves from v{version} are not supported after the "
            f"kernel-only migration."
        )


@dataclass
class SaveFile:
    """
    Represents a persisted game session save.

    Fields:
        save_id:        Unique identifier for this save
        player_id:      Player who owns this save
        session_data:   Full serializable session state dict
        timestamp:      ISO-format datetime string of when the save was created
        schema_version: Version string for migration support
    """
    save_id: str
    player_id: str
    session_data: Dict[str, Any]
    timestamp: str
    schema_version: str = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "save_id": self.save_id,
            "player_id": self.player_id,
            "session_data": self.session_data,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SaveFile":
        return cls(
            save_id=data["save_id"],
            player_id=data["player_id"],
            session_data=data["session_data"],
            timestamp=data["timestamp"],
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
        )
