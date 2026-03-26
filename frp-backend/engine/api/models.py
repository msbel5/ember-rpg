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
    alignment: Optional[str] = None
    skill_proficiencies: List[str] = Field(default_factory=list)
    stats: Optional[dict] = None
    creation_answers: List[dict] = Field(default_factory=list)
    creation_profile: dict = Field(default_factory=dict)


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
    initiative: Optional[int] = None
    conditions: List[str] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    death_saves: dict = Field(default_factory=dict)
    stable: bool = False


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
    conversation_state: dict = Field(default_factory=dict)


class SessionStateResponse(BaseModel):
    session_id: str
    scene: str
    location: str
    player: dict
    in_combat: bool
    turn: int
    combat: Optional[dict] = None
    active_quests: List[dict] = Field(default_factory=list)
    quest_offers: List[dict] = Field(default_factory=list)
    ground_items: List[dict] = Field(default_factory=list)
    campaign_state: dict = Field(default_factory=dict)
    conversation_state: dict = Field(default_factory=dict)
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    level: Optional[int] = None


class CreationStartRequest(BaseModel):
    player_name: str
    location: Optional[str] = None


class CreationAnswerRequest(BaseModel):
    question_id: str
    answer_id: str


class CreationFinalizeRequest(BaseModel):
    player_class: Optional[str] = None
    alignment: Optional[str] = None
    skill_proficiencies: List[str] = Field(default_factory=list)
    location: Optional[str] = None


class CreationStateResponse(BaseModel):
    creation_id: str
    player_name: str
    location: Optional[str] = None
    questions: List[dict] = Field(default_factory=list)
    answers: List[dict] = Field(default_factory=list)
    class_weights: dict = Field(default_factory=dict)
    skill_weights: dict = Field(default_factory=dict)
    alignment_axes: dict = Field(default_factory=dict)
    recommended_class: str
    recommended_alignment: str
    recommended_skills: List[str] = Field(default_factory=list)
    current_roll: List[int] = Field(default_factory=list)
    saved_roll: Optional[List[int]] = None
