"""Compatibility wrapper for focused social mixins."""
from __future__ import annotations

from engine.api.handlers.social_actions import SocialActionsMixin
from engine.api.handlers.social_state import SocialStateMixin


class SocialMixin(SocialActionsMixin, SocialStateMixin):
    """Aggregate social mixin with action and state logic split by concern."""
