"""Compatibility wrapper for focused GameEngine helper mixins."""
from __future__ import annotations

from engine.api.handlers.helper_checks import HelperChecksMixin
from engine.api.handlers.helper_world import HelperWorldMixin


class HelperMixin(HelperChecksMixin, HelperWorldMixin):
    """Aggregate helper mixin with focused implementations split by concern."""
