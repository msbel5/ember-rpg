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
    alignment: Optional[str] = None
    skill_proficiencies: List[str] = Field(default_factory=list)
    stats: Optional[Dict[str, int]] = None
    creation_answers: List[Dict[str, Any]] = Field(default_factory=list)
    creation_profile: Dict[str, Any] = Field(default_factory=dict)


class CampaignCreationStartRequest(BaseModel):
    player_name: str
    adapter_id: str = "fantasy_ember"
    profile_id: str = "standard"
    seed: Optional[int] = None
    location: Optional[str] = None


class CampaignCreationAnswerRequest(BaseModel):
    question_id: str
    answer_id: str


class CampaignCreationFinalizeRequest(BaseModel):
    player_name: Optional[str] = None
    adapter_id: Optional[str] = None
    profile_id: Optional[str] = None
    seed: Optional[int] = None
    player_class: Optional[str] = None
    alignment: Optional[str] = None
    skill_proficiencies: List[str] = Field(default_factory=list)
    assigned_stats: Optional[Dict[str, int]] = None
    creation_answers: List[Dict[str, Any]] = Field(default_factory=list)
    creation_profile: Dict[str, Any] = Field(default_factory=dict)
    location: Optional[str] = None


class CampaignCreationStateResponse(BaseModel):
    creation_id: str
    player_name: str
    adapter_id: str
    profile_id: str
    seed: int
    location: Optional[str] = None
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    class_weights: Dict[str, int] = Field(default_factory=dict)
    skill_weights: Dict[str, int] = Field(default_factory=dict)
    alignment_axes: Dict[str, int] = Field(default_factory=dict)
    recommended_class: str
    recommended_alignment: str
    recommended_skills: List[str] = Field(default_factory=list)
    current_roll: List[int] = Field(default_factory=list)
    saved_roll: Optional[List[int]] = None


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
