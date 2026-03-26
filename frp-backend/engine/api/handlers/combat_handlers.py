"""Compatibility wrapper for focused combat mixins."""
from __future__ import annotations

from engine.api.handlers.combat_actions import CombatActionsMixin
from engine.api.handlers.combat_narration import CombatNarrationMixin
from engine.api.handlers.combat_spawning import CombatSpawningMixin
from engine.api.handlers.combat_state import CombatStateMixin


class CombatMixin(CombatActionsMixin, CombatNarrationMixin, CombatSpawningMixin, CombatStateMixin):
    """Aggregate combat mixin with action, narration, and state logic split by concern."""
