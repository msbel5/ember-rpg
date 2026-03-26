"""Compatibility wrapper for focused exploration mixins."""
from __future__ import annotations

from engine.api.handlers.exploration_interaction import ExplorationInteractionMixin
from engine.api.handlers.exploration_navigation import ExplorationNavigationMixin


class ExplorationMixin(ExplorationNavigationMixin, ExplorationInteractionMixin):
    """Aggregate exploration mixin with movement and interaction logic split by concern."""
