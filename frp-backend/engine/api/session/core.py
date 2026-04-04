"""Backward-compatible re-export of CampaignSession as GameSession.

Campaign-first code should import from ``engine.api.campaign_session``
directly.  This shim exists solely so that ``engine.api.session.core``
keeps resolving for any remaining internal consumers.
"""


def __getattr__(name: str):
    """Lazy re-export to avoid circular import with campaign_session."""
    if name in ("CampaignSession", "GameSession"):
        from engine.api.campaign_session import CampaignSession
        if name == "GameSession":
            return CampaignSession
        return CampaignSession
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
