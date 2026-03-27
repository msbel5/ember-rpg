"""Pydantic models for the campaign-first API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    player_name: str
    player_class: str = "warrior"
    adapter_id: str = "fantasy_ember"
    profile_id: str = "standard"
    seed: Optional[int] = None


class CampaignCommandRequest(BaseModel):
    input: str = ""
    shortcut: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)


class CampaignSaveRequest(BaseModel):
    player_id: Optional[str] = None
    slot_name: Optional[str] = None


class CampaignSaveSummary(BaseModel):
    save_id: str
    slot_name: str
    player_id: str
    timestamp: str
    schema_version: str
    location: Optional[str] = None
    game_time: Optional[str] = None


class CampaignSaveResponse(BaseModel):
    save_id: str
    slot_name: str
    timestamp: str
    schema_version: str


class CampaignSnapshotResponse(BaseModel):
    campaign_id: str
    adapter_id: str
    profile_id: str
    narrative: str
    campaign: Dict[str, Any]


class CampaignCommandResponse(BaseModel):
    campaign_id: str
    narrative: str
    command_type: str
    hours_advanced: int
    generated_events: List[Dict[str, Any]] = Field(default_factory=list)
    campaign: Dict[str, Any]

