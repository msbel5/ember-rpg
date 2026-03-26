"""
Ember RPG - API Layer
GameEngine: orchestrates all Phase 2 systems for API actions
"""
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Dict, Any
import copy
import random

from engine.api.save_system import SaveSystem
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.character_creation import (
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    CLASS_STAT_PRIORITIES,
    CreationState,
    assign_stats_to_class,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
    roll_stat_array,
)
from engine.core.progression import ProgressionSystem
from engine.core.dm_agent import DMAIAgent, DMContext, DMEvent, SceneType, EventType
from engine.core.item import Item, ItemType
from engine.api.action_parser import ActionParser, ActionIntent, ParsedAction
from engine.api.game_session import GameSession

# Living World imports
from engine.world.proximity import check_proximity, move_cardinal, distance, astar_path
from engine.world.schedules import GameTime as LivingGameTime, hour_to_period, DEFAULT_SCHEDULES, NPCSchedule
from engine.world.tick_scheduler import WorldTickScheduler
from engine.world.naming import NameGenerator
from engine.world.npc_needs import NPCNeeds
from engine.world.need_satisfaction import NeedSatisfactionEngine
from engine.world.ethics import evaluate_action, get_faction_context, FACTION_ETHICS
from engine.world.history import HistorySeed, get_history_context, get_npc_known_facts
from engine.world.economy import LocationStock
from engine.world.rumors import RumorNetwork, NPCInfo
from engine.world.quest_timeout import QuestTracker
from engine.world.body_parts import BodyPartTracker, roll_hit_location, calculate_armor_reduction
from engine.world.caravans import CaravanManager
from engine.world.materials import apply_material, MATERIALS
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport
from engine.world.action_points import ActionPointTracker, CLASS_AP, ACTION_COSTS
from engine.world.skill_checks import (
    roll_check,
    contested_check,
    SkillCheckResult,
    ability_modifier,
    passive_score,
    saving_throw,
)
from engine.world.crafting import CraftingSystem, ALL_RECIPES, CraftingRecipe, determine_quality
from engine.world.behavior_tree import (
    BehaviorContext, create_npc_behavior_tree, Status as BTStatus,
)
from engine.map import MapData, TownGenerator


# XP rewards for killing enemies (by level)
XP_REWARDS = {1: 100, 2: 200, 3: 450, 4: 700, 5: 1100}

# NPC visual mapping: role -> (glyph, color)
NPC_VISUALS = {
    "innkeeper":   ("I", "cyan"),
    "guard":       ("G", "red"),
    "merchant":    ("$", "yellow"),
    "blacksmith":  ("B", "white"),
    "quest_giver": ("Q", "magenta"),
    "beggar":      ("b", "dim"),
    "spy":         ("s", "blue"),
    "priest":      ("P", "white"),
    "healer":      ("H", "green"),
    "sage":        ("S", "magenta"),
    "bard":        ("♪", "yellow"),
}

WORKSTATION_SPECS = {
    "forge": {"name": "Forge", "glyph": "F", "color": "bright_white"},
    "alchemy_bench": {"name": "Alchemy Bench", "glyph": "A", "color": "bright_green"},
    "workbench": {"name": "Workbench", "glyph": "W", "color": "bright_yellow"},
    "kitchen": {"name": "Kitchen", "glyph": "K", "color": "yellow"},
    "campfire": {"name": "Campfire", "glyph": "C", "color": "red"},
}

WORKSTATION_ANCHORS = {
    "forge": "forge",
    "alchemy_bench": "temple",
    "workbench": "shop",
    "kitchen": "tavern",
    "campfire": "campfire",
}

SOCIAL_ATTITUDE_DCS = {
    "friendly": {
        "no_risk": 5,
        "minor_risk": 10,
        "significant_sacrifice": 20,
    },
    "indifferent": {
        "no_risk": 10,
        "minor_risk": 15,
        "significant_sacrifice": 20,
    },
    "hostile": {
        "no_risk": 20,
        "minor_risk": 25,
        "significant_sacrifice": 999,
    },
}

DEFAULT_NPC_ATTITUDE = {
    "merchant": "indifferent",
    "blacksmith": "indifferent",
    "innkeeper": "indifferent",
    "guard": "indifferent",
    "quest_giver": "indifferent",
    "priest": "friendly",
    "healer": "friendly",
    "sage": "friendly",
    "beggar": "indifferent",
    "spy": "hostile",
}

DEFAULT_NPC_ALIGNMENT = {
    "merchant": "LN",
    "blacksmith": "LN",
    "innkeeper": "NG",
    "guard": "LG",
    "quest_giver": "NG",
    "priest": "LG",
    "healer": "NG",
    "sage": "TN",
    "beggar": "CN",
    "spy": "NE",
}

THINK_TOPIC_SKILLS = {
    "history": {"king", "empire", "war", "ruin", "lord", "queen", "history", "geçmiş", "tarih"},
    "arcana": {"magic", "spell", "glyph", "arcane", "rune", "mana", "büyü", "tılsım", "rün"},
    "religion": {"god", "saint", "temple", "holy", "prayer", "faith", "tanrı", "tapınak", "kutsal"},
    "nature": {"forest", "beast", "wolf", "herb", "road", "river", "tree", "orman", "kurt", "nehir"},
    "investigation": {"clue", "murder", "crime", "who", "why", "how", "ipuç", "cinayet", "neden"},
}

ROLE_PRODUCTION = {
    "blacksmith": ("iron_bar", "iron_sword"),
    "innkeeper": ("bread", "ale"),
    "merchant": ("torch",),
    "priest": ("healing_potion",),
}

# Starter inventory kits loaded from data/classes.json
from engine.data_loader import get_class_starting_equipment, get_class_ap_map

def _build_starter_kits() -> dict:
    """Build STARTER_KITS from data/classes.json."""
    from engine.data_loader import CLASSES
    kits = {}
    for class_id, cdata in CLASSES.items():
        kits[class_id] = cdata.get("starting_equipment", [])
    return kits

STARTER_KITS = _build_starter_kits()


@dataclass
class ActionResult:
    """
    Result of processing a player action.

    Attributes:
        narrative: DM-generated story text (shown to player)
        events: List of mechanical events that occurred
        state_changes: Dict of what changed (hp, xp, level, etc.)
        scene_type: Current scene after action
        combat_state: Combat status if in combat
        level_up: LevelUpResult if player leveled up
    """
    narrative: str
    events: list = field(default_factory=list)
    state_changes: dict = field(default_factory=dict)
    scene_type: SceneType = SceneType.EXPLORATION
    combat_state: Optional[dict] = None
    level_up: Optional[object] = None
    loot_dropped: list = field(default_factory=list)


# Default opening scenes (location, opening description)
_OPENING_SCENES = [
    ("Stone Bridge Tavern", "Low rafters, the smell of pipe smoke. A fire crackles in the hearth. The door creaks open — someone has arrived."),
    ("Forest Road", "Morning mist parts as you push forward. Branches arch overhead. A wolf howls somewhere in the distance."),
    ("Harbor Town", "Salt air fills your lungs. Fishermen haul nets at the dock. A northern-flag ship sways in the harbor."),
]


# Import handler mixins
from engine.api.handlers.helpers import HelperMixin
from engine.api.handlers.combat_handlers import CombatMixin
from engine.api.handlers.social_handlers import SocialMixin
from engine.api.handlers.exploration_handlers import ExplorationMixin
from engine.api.handlers.inventory_handlers import InventoryMixin
from engine.api.handlers.quest_handlers import QuestMixin
from engine.api.handlers.resource_handlers import ResourceMixin


class GameEngine(
    CombatMixin,
    SocialMixin,
    ExplorationMixin,
    InventoryMixin,
    QuestMixin,
    ResourceMixin,
    HelperMixin,
):
    """
    Orchestrates all game systems for API-level action processing.

    The engine translates player natural language into game mechanics,
    resolves outcomes, and returns DM narrative.

    Usage:
        engine = GameEngine()
        session = engine.new_session("Aria", "warrior")
        result = engine.process_action(session, "attack the goblin")
    """

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        """
        Initialize game engine.

        Args:
            llm: Optional LLM backend callable(prompt) -> str.
                 If None, template-based narration is used.
        """
        self.parser = ActionParser()
        self.dm = DMAIAgent()
        self.progression = ProgressionSystem()
        self.llm = llm
        self.save_system = SaveSystem()
        # Living World shared systems
        self.tick_scheduler = WorldTickScheduler()
        self.need_satisfaction = NeedSatisfactionEngine()

    def new_session(
        self,
        player_name: str,
        player_class: str = "warrior",
        location: Optional[str] = None,
        *,
        alignment: Optional[str] = None,
        skill_proficiencies: Optional[List[str]] = None,
        stats: Optional[Dict[str, int]] = None,
        creation_answers: Optional[List[Dict[str, Any]]] = None,
        creation_profile: Optional[Dict[str, Any]] = None,
    ) -> GameSession:
        """
        Create a new game session for a player.

        Args:
            player_name: Player character name
            player_class: Starting class (warrior/rogue/mage/priest)
            location: Starting location name (random if None)

        Returns:
            Initialized GameSession
        """
        class_stats = {
            "warrior": {"MIG": 16, "AGI": 12, "END": 14, "MND": 8,  "INS": 10, "PRE": 10},
            "rogue":   {"MIG": 10, "AGI": 16, "END": 10, "MND": 10, "INS": 14, "PRE": 12},
            "mage":    {"MIG": 8,  "AGI": 12, "END": 10, "MND": 16, "INS": 14, "PRE": 10},
            "priest":  {"MIG": 10, "AGI": 10, "END": 12, "MND": 14, "INS": 16, "PRE": 12},
        }
        class_hp = {"warrior": 20, "rogue": 16, "mage": 12, "priest": 16}
        class_sp = {"warrior": 0,  "rogue": 0,  "mage": 16, "priest": 12}

        requested_class = str(player_class or "warrior").lower()
        player_class = {
            "fighter": "warrior",
            "cleric": "priest",
            "thief": "rogue",
            "wizard": "mage",
        }.get(requested_class, requested_class)
        unknown_class = player_class not in class_stats
        if unknown_class:
            player_class = "warrior"
        class_stats_template = class_stats.get(player_class, class_stats["warrior"])
        assigned_stats = dict(stats or {})
        if assigned_stats:
            for key in ("MIG", "AGI", "END", "MND", "INS", "PRE"):
                assigned_stats.setdefault(key, 10)
        else:
            assigned_stats = dict(class_stats_template)
        hp    = 16 if unknown_class else class_hp.get(player_class, 16)
        sp    = class_sp.get(player_class, 0)

        creation_profile = dict(creation_profile or {})
        recommended_axes = dict(creation_profile.get("alignment_axes") or {})
        effective_alignment = alignment or recommended_alignment_from_axes(recommended_axes) if recommended_axes else (alignment or "TN")
        default_skills = recommended_skills_for_class(
            {"skill_weights": creation_profile.get("skill_weights", {})},
            player_class,
        )
        selected_skills = list(skill_proficiencies or default_skills or CLASS_DEFAULT_SKILLS.get(player_class, []))
        allowed_skills = set(CLASS_SKILL_OPTIONS.get(player_class, []))
        selected_skills = [skill for skill in selected_skills if skill in allowed_skills][: CLASS_SKILL_COUNTS.get(player_class, 2)]
        if len(selected_skills) < CLASS_SKILL_COUNTS.get(player_class, 2):
            for fallback in CLASS_DEFAULT_SKILLS.get(player_class, []):
                if fallback in allowed_skills and fallback not in selected_skills:
                    selected_skills.append(fallback)
                if len(selected_skills) >= CLASS_SKILL_COUNTS.get(player_class, 2):
                    break

        player = Character(
            name=player_name,
            classes={player_class: 1},
            stats=assigned_stats,
            hp=hp, max_hp=hp,
            spell_points=sp, max_spell_points=sp,
            level=1, xp=0,
            skill_proficiencies=selected_skills,
            alignment=effective_alignment or "TN",
            creation_answers=list(creation_answers or []),
            creation_profile=creation_profile,
            use_death_saves=True,
        )
        player.set_alignment_from_axes() if not alignment and recommended_axes else None
        player.sync_derived_progression()

        if location is None:
            loc, _ = _OPENING_SCENES[0]
        else:
            loc = location

        dm_context = DMContext(
            scene_type=SceneType.EXPLORATION,
            location=loc,
            party=[player],
        )

        session = GameSession(player=player, dm_context=dm_context)

        # --- Initialize Living World systems ---
        # Generate world history from session seed
        seed = hash(session.session_id) % 1000000
        session.history_seed = HistorySeed().generate(seed=seed)
        session.name_gen = NameGenerator(seed=seed)

        # Scale body tracker HP to player's max_hp
        hp_scale = player.max_hp / 20.0  # 20 is baseline warrior HP
        for part in session.body_tracker.max_hp:
            session.body_tracker.max_hp[part] = max(1, int(session.body_tracker.max_hp[part] * hp_scale))
            session.body_tracker.current_hp[part] = session.body_tracker.max_hp[part]

        # Update location stock ID to match starting location
        session.location_stock = LocationStock(
            location_id=loc.lower().replace(" ", "_"),
            baseline={"food": 20, "ale": 10, "iron_bar": 5, "bread": 15,
                      "healing_potion": 3, "leather": 8, "cloth": 10},
        )

        # Populate initial entities with procedural names
        self._populate_scene_entities(session, loc)

        # --- Give starter inventory based on class ---
        pclass = player_class.lower()
        kit = STARTER_KITS.get(pclass, STARTER_KITS["warrior"])
        for item_template in kit:
            item = dict(item_template)  # shallow copy
            slot = item.get("slot")
            # Auto-equip weapon/armor/shield
            if slot and session.equipment.get(slot) is None:
                session.set_equipment_slot(slot, item)
                # Update AP tracker armor type for armor items
                if slot == "armor" and session.ap_tracker:
                    material = item.get("material", "none")
                    # Map material to armor weight category
                    armor_weight_map = {
                        "cloth": "cloth", "leather": "leather",
                        "iron": "chain_mail", "steel": "plate_armor",
                    }
                    session.ap_tracker.set_armor(armor_weight_map.get(material, "none"))
            else:
                session.add_item(item)

        session.quest_offers = GameSession.merge_quest_offers(
            session.quest_offers,
            self._generate_emergent_quests(session, force=True),
            new_default_source="emergent",
        )
        session.narration_context["last_world_tick_hour"] = self._current_game_hour(session)
        session.ensure_consistency()
        return session

    def process_action(self, session: GameSession, input_text: str) -> ActionResult:
        """
        Process a player's natural language action.

        Args:
            session: Current game session (mutated in-place)
            input_text: Player's raw text input

        Returns:
            ActionResult with narrative and state changes
        """
        session.ensure_consistency()
        action = self.parser.parse(input_text)
        if action.intent == ActionIntent.UNKNOWN:
            target_type = session.conversation_state.get("target_type")
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

        handlers = {
            ActionIntent.ATTACK:     self._handle_attack,
            ActionIntent.CAST_SPELL: self._handle_spell,
            ActionIntent.USE_ITEM:   self._handle_use_item,
            ActionIntent.EXAMINE:    self._handle_examine,
            ActionIntent.LOOK:       self._handle_look,
            ActionIntent.TALK:       self._handle_talk,
            ActionIntent.ADDRESS:    self._handle_address,
            ActionIntent.ACCEPT_QUEST: self._handle_accept_quest,
            ActionIntent.TURN_IN_QUEST: self._handle_turn_in_quest,
            ActionIntent.REST:       self._handle_rest,
            ActionIntent.SHORT_REST: self._handle_short_rest,
            ActionIntent.LONG_REST:  self._handle_long_rest,
            ActionIntent.MOVE:       self._handle_move,
            ActionIntent.OPEN:       self._handle_open,
            ActionIntent.TRADE:      self._handle_trade,
            ActionIntent.FLEE:       self._handle_flee,
            ActionIntent.DISENGAGE:  self._handle_disengage,
            ActionIntent.INVENTORY:  self._handle_inventory,
            ActionIntent.PICK_UP:    self._handle_pickup,
            ActionIntent.DROP:       self._handle_drop,
            ActionIntent.EQUIP:      self._handle_equip,
            ActionIntent.UNEQUIP:    self._handle_unequip,
            ActionIntent.CRAFT:      self._handle_craft,
            ActionIntent.SEARCH:     self._handle_search,
            ActionIntent.STEAL:      self._handle_steal,
            ActionIntent.PERSUADE:   self._handle_persuade,
            ActionIntent.INTIMIDATE: self._handle_intimidate,
            ActionIntent.BRIBE:      self._handle_bribe,
            ActionIntent.DECEIVE:    self._handle_deceive,
            ActionIntent.THINK:      self._handle_think,
            ActionIntent.SNEAK:      self._handle_sneak,
            ActionIntent.CLIMB:      self._handle_climb,
            ActionIntent.LOCKPICK:   self._handle_lockpick,
            ActionIntent.PRAY:       self._handle_pray,
            ActionIntent.READ_ITEM:  self._handle_read_item,
            ActionIntent.PUSH:       self._handle_push,
            ActionIntent.FISH:       self._handle_fish,
            ActionIntent.MINE:       self._handle_mine,
            ActionIntent.CHOP:       self._handle_chop,
            ActionIntent.FILL:       self._handle_fill,
            ActionIntent.POUR:       self._handle_pour,
            ActionIntent.EMPTY:      self._handle_pour,   # empty = pour out
            ActionIntent.STASH:      self._handle_stash,
            ActionIntent.ROTATE_ITEM: self._handle_rotate_item,
            ActionIntent.GO_TO:      self._handle_go_to,
            ActionIntent.UNKNOWN:    self._handle_unknown,
        }

        if action.intent == ActionIntent.ROTATE_ITEM:
            session.touch()
            result = handlers.get(action.intent, self._handle_unknown)(session, action)
            session.sync_player_state()
            return result

        session.touch()
        session.dm_context.advance_turn()

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

    def _world_tick(self, session: GameSession, minutes: int = 15, refresh_ap: bool = False) -> list:
        """Advance game time and run all Living World subsystems."""
        events: List[Dict[str, Any]] = []
        if not getattr(session, "game_time", None):
            return events

        remaining_minutes = max(0, int(minutes))
        if remaining_minutes == 0:
            return events

        world_period_changed = False
        final_hour = self._current_game_hour(session)
        step_size = 15

        while remaining_minutes > 0:
            step_minutes = min(step_size, remaining_minutes)
            before_hour = self._current_game_hour(session)
            previous_period = session.game_time.period
            session.game_time.advance(step_minutes)
            session.clear_expired_timed_conditions()
            after_hour = self._current_game_hour(session)
            final_hour = after_hour
            hours_passed = step_minutes / 60.0
            current_period = session.game_time.period
            world_period_changed = world_period_changed or (previous_period != current_period)

            for entity_id, entity in session.entities.items():
                needs = entity.get("needs")
                if isinstance(needs, NPCNeeds):
                    needs.tick(hours=hours_passed)
                schedule = entity.get("schedule")
                if isinstance(schedule, NPCSchedule):
                    entity["scheduled_location"] = schedule.get_location(current_period)

            if session.spatial_index:
                npc_entities = session.spatial_index.entities_of_type(EntityType.NPC)
                for npc in npc_entities:
                    if npc.id == "player" or not npc.is_alive():
                        continue
                    tree = create_npc_behavior_tree(is_guard=(npc.job == "guard"))
                    hostiles = [session.player_entity] if npc.is_hostile() and session.player_entity else []
                    ctx = BehaviorContext(
                        entity=npc,
                        spatial_index=session.spatial_index,
                        game_time=session.game_time,
                        map_data=session.map_data,
                        hostiles=hostiles,
                    )
                    tree.tick(ctx)
                    action_type = ctx.blackboard.get("action")
                    target_pos = ctx.blackboard.get("target_pos")

                    if action_type == "follow_schedule" and isinstance(npc.schedule, NPCSchedule):
                        scheduled_pos = npc.schedule.get_position(current_period)
                        if scheduled_pos:
                            target_pos = tuple(scheduled_pos)

                    if target_pos and action_type in {"wander", "flee", "patrol", "move_toward_hostile", "follow_schedule"}:
                        target_pos = tuple(target_pos)
                        step_target = self._step_toward(tuple(npc.position), target_pos)
                        moved = self._move_entity_if_possible(session, npc, step_target)
                        if moved:
                            if npc.id in session.entities:
                                session.sync_entity_record(npc.id, npc)
                            if action_type == "follow_schedule":
                                destination = getattr(npc.schedule, "get_location", lambda _period: "their post")(current_period)
                            else:
                                destination = action_type.replace("_", " ")
                            events.append({
                                "type": "npc_move",
                                "npc_id": npc.id,
                                "npc_name": npc.name,
                                "position": [npc.position[0], npc.position[1]],
                                "destination": destination,
                            })

            # Include current hour if tick starts exactly on the hour boundary
            # (before_hour=47.0, after_hour=47.25 -> should include hour 47)
            start_hour = int(before_hour) if before_hour == int(before_hour) else int(before_hour) + 1
            crossed_hours = list(range(start_hour, int(after_hour) + 1))
            for hour_marker in crossed_hours:
                if session.ap_tracker is not None:
                    session.ap_tracker.refresh()
                self._run_hourly_world_updates(session, hour_marker, events)
                quest_result = session.quest_tracker.tick(float(hour_marker))
                expired = list(quest_result.get("expired") or [])
                reminders = list(quest_result.get("reminders") or [])
                if expired:
                    failed = session.campaign_state.setdefault("failed_quests", [])
                    failed_ids = session.campaign_state.setdefault("failed_quest_ids", [])
                    accepted = session.campaign_state.setdefault("accepted_quests", [])
                    for event in expired:
                        quest_id = event.get("quest_id")
                        if quest_id and quest_id not in failed:
                            failed.append(quest_id)
                        if quest_id and quest_id not in failed_ids:
                            failed_ids.append(quest_id)
                        if quest_id in accepted:
                            accepted.remove(quest_id)
                    events.extend(expired)
                if reminders:
                    events.extend(reminders)

            # Emergent quest generation only on hour boundaries (not every 15-min step)
            if crossed_hours:
                session.quest_offers = GameSession.merge_quest_offers(
                    session.quest_offers,
                    self._generate_emergent_quests(session),
                    new_default_source="emergent",
                )
            remaining_minutes -= step_minutes

        session.campaign_state["last_world_tick_hour"] = final_hour
        session.narration_context["world_period_changed"] = world_period_changed
        return events

    def _build_world_context(self, session: GameSession) -> str:
        """Assemble all Living World state into a context string for LLM prompts."""
        parts = []

        # Time
        if session.game_time:
            parts.append(f"[Time: {session.game_time.to_string()}]")

        # NPCs at current location
        nearby = []
        for eid, entity in session.entities.items():
            ent_pos = entity.get("position", [0, 0])
            dist = max(abs(session.position[0] - ent_pos[0]),
                       abs(session.position[1] - ent_pos[1]))
            if dist <= 3:
                needs = entity.get("needs")
                mood = needs.emotional_state() if isinstance(needs, NPCNeeds) else "content"
                nearby.append(f"  {entity['name']} ({entity['role']}, {entity['faction']}) — mood: {mood}")
        if nearby:
            parts.append("[Nearby NPCs]\n" + "\n".join(nearby))

        # Faction context for nearby NPCs
        factions_seen = set()
        for eid, entity in session.entities.items():
            faction = entity.get("faction", "")
            if faction and faction in FACTION_ETHICS and faction not in factions_seen:
                factions_seen.add(faction)
                ctx = get_faction_context(faction)
                parts.append(f"[Faction: {faction}] Values: {', '.join(ctx['top_values'])}. Personality: {ctx['personality']}")

        # History context (abbreviated)
        if session.history_seed:
            tensions = session.history_seed.get_tensions()
            if tensions:
                tension_strs = [t.name for t in tensions[:3]]
                parts.append("[Current Tensions] " + "; ".join(tension_strs))

        # Active rumors at this location
        active_rumors = session.rumor_network.get_all_active()
        if active_rumors:
            rumor_strs = [f"'{r.fact}' (confidence: {r.confidence:.0%})" for r in active_rumors[:3]]
            parts.append("[Rumors] " + "; ".join(rumor_strs))

        # Economy: notable prices
        price_notes = []
        for item in ["food", "iron_bar", "healing_potion"]:
            mod = session.location_stock.get_price_modifier(item)
            if mod != 1.0:
                price_notes.append(f"{item}: {mod:.1f}x price")
        if price_notes:
            parts.append("[Economy] " + ", ".join(price_notes))

        # Active quests
        active_quests = session.quest_tracker.get_active_quests()
        if active_quests:
            quest_strs = [f"'{q.title}'" + (f" (deadline in {q.deadline_hour - (session.game_time.hour + (session.game_time.day-1)*24):.0f}h)" if q.deadline_hour else "")
                          for q in active_quests[:3]]
            parts.append("[Active Quests] " + "; ".join(quest_strs))
        elif session.quest_offers:
            offer_strs = [f"'{offer['title']}'" for offer in session.quest_offers[:2] if offer.get("title")]
            if offer_strs:
                parts.append("[Quest Leads] " + "; ".join(offer_strs))

        # Body injuries
        injuries = session.body_tracker.get_injury_effects()
        if injuries:
            inj_strs = [f"{part}: {status}" for part, status in injuries.items()]
            parts.append("[Player Injuries] " + ", ".join(inj_strs))

        return "\n".join(parts)
