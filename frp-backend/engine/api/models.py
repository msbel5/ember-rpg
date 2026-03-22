"""
Ember RPG - API Layer
Pydantic request/response models
"""
from pydantic import BaseModel
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
    state_changes: dict = {}
    level_up: Optional[dict] = None


class SessionStateResponse(BaseModel):
    session_id: str
    scene: str
    location: str
    player: dict
    in_combat: bool
    turn: int
