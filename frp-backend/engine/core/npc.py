"""
Ember RPG - NPC Template System
NPCManager: loads NPC templates from data/npcs/npcs.json,
provides dialogue retrieval and relationship management.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.data_loader import load_registry_list_from_path

# Default path relative to this file's package root
_DEFAULT_NPC_PATH = Path(__file__).parent.parent.parent / "data" / "npcs" / "npcs.json"

# Required top-level fields for each NPC template
REQUIRED_FIELDS = {
    "id", "name", "race", "role", "faction_alignment",
    "personality", "dialogue_snippets", "relationship_modifiers"
}

# Required sub-fields
REQUIRED_PERSONALITY = {"traits", "motivations", "fears"}
REQUIRED_DIALOGUE = {"greetings", "farewells", "idle", "quest_related"}


class NPCValidationError(Exception):
    """Raised when an NPC template fails validation."""


def _validate_npc(npc: Dict[str, Any]) -> None:
    """Validate a single NPC dict. Raises NPCValidationError on failure."""
    missing = REQUIRED_FIELDS - set(npc.keys())
    if missing:
        raise NPCValidationError(
            f"NPC '{npc.get('id', '?')}' missing required fields: {missing}"
        )

    personality = npc["personality"]
    missing_p = REQUIRED_PERSONALITY - set(personality.keys())
    if missing_p:
        raise NPCValidationError(
            f"NPC '{npc['id']}' personality missing: {missing_p}"
        )

    dialogue = npc["dialogue_snippets"]
    missing_d = REQUIRED_DIALOGUE - set(dialogue.keys())
    if missing_d:
        raise NPCValidationError(
            f"NPC '{npc['id']}' dialogue_snippets missing: {missing_d}"
        )

    # Each dialogue category must have at least one line
    for category in REQUIRED_DIALOGUE:
        lines = dialogue[category]
        if not isinstance(lines, list) or len(lines) == 0:
            raise NPCValidationError(
                f"NPC '{npc['id']}' dialogue_snippets['{category}'] must be a non-empty list"
            )

    # relationship_modifiers must be a dict of str -> int/float
    rm = npc["relationship_modifiers"]
    if not isinstance(rm, dict):
        raise NPCValidationError(
            f"NPC '{npc['id']}' relationship_modifiers must be a dict"
        )
    for key, val in rm.items():
        if not isinstance(val, (int, float)):
            raise NPCValidationError(
                f"NPC '{npc['id']}' relationship_modifiers['{key}'] must be numeric"
            )


class NPCManager:
    """
    Manages NPC templates loaded from a JSON file.

    Usage::

        manager = NPCManager()
        manager.load()                        # loads default path
        npc = manager.get("merchant_bram")    # fetch by id
        line = manager.get_dialogue(npc, "greetings")   # random dialogue line
        manager.modify_relationship(npc, "completed_quest")  # apply modifier
    """

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self._data_path: Path = Path(data_path) if data_path else _DEFAULT_NPC_PATH
        self._npcs: Dict[str, Dict[str, Any]] = {}
        # Per-NPC runtime relationship scores {npc_id: float}
        self._relationships: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def load(self, data_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Load and validate NPC templates from JSON.

        Args:
            data_path: Optional override for the JSON file path.

        Returns:
            List of loaded NPC dicts.

        Raises:
            FileNotFoundError: if the JSON file doesn't exist.
            NPCValidationError: if any NPC fails validation.
        """
        path = Path(data_path) if data_path else self._data_path
        if not path.exists():
            raise FileNotFoundError(f"NPC data file not found: {path}")

        npcs_list: List[Dict[str, Any]] = load_registry_list_from_path(path, "npcs")
        loaded: Dict[str, Dict[str, Any]] = {}
        for npc in npcs_list:
            _validate_npc(npc)
            loaded[npc["id"]] = npc

        self._npcs = loaded
        # Initialise relationships for new NPCs
        for npc_id in self._npcs:
            if npc_id not in self._relationships:
                self._relationships[npc_id] = 0.0

        return list(loaded.values())

    def get(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an NPC template by id.

        Args:
            npc_id: The NPC's unique id string.

        Returns:
            The NPC dict, or None if not found.
        """
        return self._npcs.get(npc_id)

    def get_dialogue(
        self,
        npc: Dict[str, Any],
        category: str,
        random_pick: bool = True,
    ) -> str:
        """
        Get a dialogue line from an NPC for a given category.

        Args:
            npc: NPC dict (as returned by get()).
            category: One of 'greetings', 'farewells', 'idle', 'quest_related'.
            random_pick: If True, return a random line; otherwise return the first.

        Returns:
            A dialogue string.

        Raises:
            KeyError: if the category doesn't exist.
            ValueError: if the NPC dict is invalid.
        """
        if "dialogue_snippets" not in npc:
            raise ValueError(f"NPC '{npc.get('id', '?')}' has no dialogue_snippets")

        lines: List[str] = npc["dialogue_snippets"][category]
        if not lines:
            raise ValueError(
                f"NPC '{npc.get('id', '?')}' has no lines in category '{category}'"
            )

        return random.choice(lines) if random_pick else lines[0]

    def modify_relationship(
        self,
        npc: Dict[str, Any],
        action: str,
        custom_delta: Optional[float] = None,
    ) -> float:
        """
        Apply a relationship modifier to an NPC based on a player action.

        Args:
            npc: NPC dict (as returned by get()).
            action: Key in the NPC's relationship_modifiers dict.
            custom_delta: If provided, use this value instead of the template value.

        Returns:
            The new relationship score (clamped to [-100, 100]).

        Raises:
            KeyError: if the action isn't in relationship_modifiers and no custom_delta.
        """
        npc_id: str = npc["id"]
        current: float = self._relationships.get(npc_id, 0.0)

        if custom_delta is not None:
            delta = custom_delta
        else:
            delta = npc["relationship_modifiers"][action]

        new_score = max(-100.0, min(100.0, current + delta))
        self._relationships[npc_id] = new_score
        return new_score

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def get_relationship(self, npc: Dict[str, Any]) -> float:
        """Return the current relationship score for an NPC."""
        return self._relationships.get(npc["id"], 0.0)

    def list_npcs(self) -> List[Dict[str, Any]]:
        """Return all loaded NPC templates."""
        return list(self._npcs.values())

    def get_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Return all NPCs with a given role."""
        return [n for n in self._npcs.values() if n["role"] == role]

    def get_by_faction(self, faction: str) -> List[Dict[str, Any]]:
        """Return all NPCs aligned to a given faction."""
        return [n for n in self._npcs.values() if n["faction_alignment"] == faction]

    def reset_relationship(self, npc: Dict[str, Any]) -> None:
        """Reset a single NPC's relationship score to 0."""
        self._relationships[npc["id"]] = 0.0
