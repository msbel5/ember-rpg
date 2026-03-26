"""Ember RPG API layer orchestration surface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from engine.api.action_parser import ActionIntent, ActionParser, ParsedAction
from engine.api.game_engine_runtime import GameEngineRuntimeMixin
from engine.api.game_session import GameSession
from engine.api.handlers.combat_handlers import CombatMixin
from engine.api.handlers.exploration_handlers import ExplorationMixin
from engine.api.handlers.helpers import HelperMixin
from engine.api.handlers.inventory_handlers import InventoryMixin
from engine.api.handlers.quest_handlers import QuestMixin
from engine.api.handlers.resource_handlers import ResourceMixin
from engine.api.handlers.social_handlers import SocialMixin
from engine.api.runtime_constants import (
    CLASS_ALIASES,
    DEFAULT_NPC_ALIGNMENT,
    DEFAULT_NPC_ATTITUDE,
    DEFAULT_OPENING_SCENE,
    DEFAULT_PLAYER_CLASS,
    HOSTILE_KEYWORDS,
    INTERACTION_HOLD_TURNS,
    LOCATION_STOCK_BASELINE,
    NPC_VISUALS,
    OPENING_SCENES,
    ROLE_PRODUCTION,
    SOCIAL_ATTITUDE_DCS,
    STARTER_KITS,
    THINK_TOPIC_SKILLS,
    WORKSTATION_ANCHORS,
    WORKSTATION_SPECS,
    XP_REWARDS,
)
from engine.api.save_system import SaveSystem
from engine.core.dm_agent import DMAIAgent, SceneType
from engine.core.progression import ProgressionSystem
from engine.world.body_parts import roll_hit_location
from engine.world.need_satisfaction import NeedSatisfactionEngine
from engine.world.skill_checks import SkillCheckResult, ability_modifier, contested_check, passive_score, roll_check, saving_throw
from engine.world.tick_scheduler import WorldTickScheduler


@dataclass
class ActionResult:
    """Result of processing a player action."""

    narrative: str
    events: list = field(default_factory=list)
    state_changes: dict = field(default_factory=dict)
    scene_type: SceneType = SceneType.EXPLORATION
    combat_state: Optional[dict] = None
    level_up: Optional[object] = None
    loot_dropped: list = field(default_factory=list)


class GameEngine(
    GameEngineRuntimeMixin,
    CombatMixin,
    SocialMixin,
    ExplorationMixin,
    InventoryMixin,
    QuestMixin,
    ResourceMixin,
    HelperMixin,
):
    """Public orchestration surface for API-level action processing."""

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        self.parser = ActionParser()
        self.dm = DMAIAgent()
        self.progression = ProgressionSystem()
        self.llm = llm
        self.save_system = SaveSystem()
        self.tick_scheduler = WorldTickScheduler()
        self.need_satisfaction = NeedSatisfactionEngine()

    def process_action(self, session: GameSession, input_text: str) -> ActionResult:
        session.ensure_consistency()
        action = self.parser.parse(input_text)
        target_type = session.conversation_state.get("target_type")
        if action.intent == ActionIntent.UNKNOWN:
            if target_type == "npc" and input_text.strip():
                action = ParsedAction(
                    intent=ActionIntent.ADDRESS,
                    raw_input=input_text.strip(),
                    target=session.conversation_state.get("npc_name"),
                    action_detail=input_text.strip(),
                )
            elif target_type == "self" and input_text.strip():
                action = ParsedAction(
                    intent=ActionIntent.THINK,
                    raw_input=input_text.strip(),
                    target=input_text.strip(),
                    action_detail=input_text.strip(),
                )
        elif action.intent == ActionIntent.ADDRESS and target_type == "npc":
            current_target = session.conversation_state.get("npc_name")
            parsed_target = (action.target or "").strip()
            if current_target and (not parsed_target or self._find_entity_by_name(session, parsed_target) is None):
                action = ParsedAction(
                    intent=ActionIntent.ADDRESS,
                    raw_input=input_text.strip(),
                    target=current_target,
                    action_detail=input_text.strip(),
                )

        system_handlers = {
            ActionIntent.SAVE_GAME: self._handle_save_game,
            ActionIntent.LOAD_GAME: self._handle_load_game,
            ActionIntent.LIST_SAVES: self._handle_list_saves,
            ActionIntent.DELETE_SAVE: self._handle_delete_save,
        }
        if action.intent in system_handlers:
            result = system_handlers[action.intent](session, action)
            session.ensure_consistency()
            return result

        # Allowlist approach: only these intents are valid during combat
        _COMBAT_ALLOWED = {
            ActionIntent.ATTACK, ActionIntent.CAST_SPELL, ActionIntent.FLEE,
            ActionIntent.DISENGAGE, ActionIntent.USE_ITEM, ActionIntent.INVENTORY,
            ActionIntent.LOOK, ActionIntent.EXAMINE, ActionIntent.EQUIP,
            ActionIntent.UNEQUIP, ActionIntent.MOVE, ActionIntent.PICK_UP,
            ActionIntent.DROP,
        }
        if session.in_combat() and action.intent not in _COMBAT_ALLOWED:
            return ActionResult(
                narrative="You can't do that during combat!",
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(session.combat) if session.combat is not None else None,
                state_changes={"_skip_world_tick": True},
            )

        handlers = {
            ActionIntent.ATTACK: self._handle_attack,
            ActionIntent.CAST_SPELL: self._handle_spell,
            ActionIntent.USE_ITEM: self._handle_use_item,
            ActionIntent.EXAMINE: self._handle_examine,
            ActionIntent.LOOK: self._handle_look,
            ActionIntent.TALK: self._handle_talk,
            ActionIntent.ADDRESS: self._handle_address,
            ActionIntent.ACCEPT_QUEST: self._handle_accept_quest,
            ActionIntent.TURN_IN_QUEST: self._handle_turn_in_quest,
            ActionIntent.REST: self._handle_rest,
            ActionIntent.SHORT_REST: self._handle_short_rest,
            ActionIntent.LONG_REST: self._handle_long_rest,
            ActionIntent.MOVE: self._handle_move,
            ActionIntent.OPEN: self._handle_open,
            ActionIntent.TRADE: self._handle_trade,
            ActionIntent.FLEE: self._handle_flee,
            ActionIntent.DISENGAGE: self._handle_disengage,
            ActionIntent.INVENTORY: self._handle_inventory,
            ActionIntent.PICK_UP: self._handle_pickup,
            ActionIntent.DROP: self._handle_drop,
            ActionIntent.EQUIP: self._handle_equip,
            ActionIntent.UNEQUIP: self._handle_unequip,
            ActionIntent.CRAFT: self._handle_craft,
            ActionIntent.SEARCH: self._handle_search,
            ActionIntent.STEAL: self._handle_steal,
            ActionIntent.PERSUADE: self._handle_persuade,
            ActionIntent.INTIMIDATE: self._handle_intimidate,
            ActionIntent.BRIBE: self._handle_bribe,
            ActionIntent.DECEIVE: self._handle_deceive,
            ActionIntent.THINK: self._handle_think,
            ActionIntent.SNEAK: self._handle_sneak,
            ActionIntent.CLIMB: self._handle_climb,
            ActionIntent.LOCKPICK: self._handle_lockpick,
            ActionIntent.PRAY: self._handle_pray,
            ActionIntent.READ_ITEM: self._handle_read_item,
            ActionIntent.PUSH: self._handle_push,
            ActionIntent.FISH: self._handle_fish,
            ActionIntent.MINE: self._handle_mine,
            ActionIntent.CHOP: self._handle_chop,
            ActionIntent.FILL: self._handle_fill,
            ActionIntent.POUR: self._handle_pour,
            ActionIntent.EMPTY: self._handle_pour,
            ActionIntent.STASH: self._handle_stash,
            ActionIntent.ROTATE_ITEM: self._handle_rotate_item,
            ActionIntent.GO_TO: self._handle_go_to,
            ActionIntent.UNKNOWN: self._handle_unknown,
        }

        if action.intent == ActionIntent.ROTATE_ITEM:
            session.touch()
            result = handlers.get(action.intent, self._handle_unknown)(session, action)
            session.sync_player_state()
            return result

        session.touch()
        session.dm_context.advance_turn()

        # Auto-turn: if AP is 0 outside combat, refresh and tick world forward
        if (
            session.ap_tracker is not None
            and session.ap_tracker.current_ap <= 0
            and not session.in_combat()
        ):
            session.ap_tracker.refresh()
            self._world_tick(session, minutes=60, refresh_ap=True)

        handler = handlers.get(action.intent, self._handle_unknown)
        result = handler(session, action)

        world_minutes = int(result.state_changes.pop("_world_minutes", 15)) if result.state_changes else 15
        skip_world_tick = bool(result.state_changes.pop("_skip_world_tick", False)) if result.state_changes else False
        if not skip_world_tick:
            world_events = self._world_tick(
                session,
                minutes=world_minutes,
                refresh_ap=(action.intent in {ActionIntent.REST, ActionIntent.SHORT_REST, ActionIntent.LONG_REST}),
            )
            self._merge_world_events(session, result, world_events)

        pending_ap_after = result.state_changes.pop("_ap_after_world_tick", None) if result.state_changes else None
        if pending_ap_after is not None and session.ap_tracker is not None:
            session.ap_tracker.current_ap = max(0, min(session.ap_tracker.max_ap, int(pending_ap_after)))

        auto_refresh = bool(session.narration_context.pop("_auto_refresh_after_action", False))
        if (
            auto_refresh
            and pending_ap_after is None
            and session.ap_tracker is not None
            and not session.in_combat()
            and session.ap_tracker.current_ap <= 0
        ):
            session.ap_tracker.refresh()
            result.narrative = f"{result.narrative} (New turn — AP refreshed)"

        self._clear_conversation_if_invalid(session)
        session.sync_player_state()
        return result
