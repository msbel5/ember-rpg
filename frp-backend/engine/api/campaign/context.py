"""Shared dataclasses for campaign-first runtime state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.api.game_session import GameSession
from engine.kernel.creation import CreationState
from engine.worldgen.models import RegionSnapshot, WorldBlueprint


@dataclass
class CampaignContext:
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int
    world: WorldBlueprint
    session: GameSession
    region_snapshot: RegionSnapshot
    settlement_state: dict[str, Any]
    recent_event_log: list[dict[str, Any]] = field(default_factory=list)
    kernel_runtime: dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignCreationContext:
    state: CreationState
    adapter_id: str
    profile_id: str
    seed: int
    location: Optional[str] = None


__all__ = ["CampaignContext", "CampaignCreationContext"]
