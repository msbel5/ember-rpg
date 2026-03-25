"""
Ember RPG - API Layer
Pydantic request/response models
"""
from pydantic import BaseModel
from pydantic import Field
from typing import Optional, List


class NewSessionRequest(BaseModel):
    player_name: str
    player_class: str = "warrior"
    location: Optional[str] = None


class NewSessionResponse(BaseModel):
    session_id: str
    narrative: str
    player: dict
    scene: str
    location: str


class ActionRequest(BaseModel):
    input: str


class CombatantState(BaseModel):
    name: str
    hp: int
    max_hp: int
    ap: int
    dead: bool


class CombatState(BaseModel):
    round: int
    active: Optional[str]
    ended: bool
    combatants: List[CombatantState]


class ActionResponse(BaseModel):
    narrative: str
    scene: str
    player: dict
    combat: Optional[dict] = None
    state_changes: dict = Field(default_factory=dict)
    level_up: Optional[dict] = None
    active_quests: List[dict] = Field(default_factory=list)
    quest_offers: List[dict] = Field(default_factory=list)
    ground_items: List[dict] = Field(default_factory=list)
    campaign_state: dict = Field(default_factory=dict)


class SessionStateResponse(BaseModel):
    session_id: str
    scene: str
    location: str
    player: dict
    in_combat: bool
    turn: int
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    level: Optional[int] = None
