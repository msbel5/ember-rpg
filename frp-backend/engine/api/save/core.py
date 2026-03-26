"""Focused SaveSystem implementation."""
from __future__ import annotations

from pathlib import Path

from .combat_state import SaveCombatStateMixin
from .constants import SAVE_DIR
from .repository import SaveRepositoryMixin
from .session_state import SaveSessionStateMixin


class SaveSystem(SaveCombatStateMixin, SaveSessionStateMixin, SaveRepositoryMixin):
    """Game save/load manager composed from focused helpers."""

    def __init__(self, save_dir: Path = SAVE_DIR):
        super().__init__(save_dir=save_dir)
