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
from engine.core.progression import ProgressionSystem
from engine.core.dm_agent import DMAIAgent, DMContext, DMEvent, SceneType, EventType
from engine.core.item import Item, ItemType
from engine.api.action_parser import ActionParser, ActionIntent, ParsedAction
from engine.api.game_session import GameSession

# Living World imports
from engine.world.proximity import check_proximity, move_cardinal, distance
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
from engine.world.skill_checks import roll_check, contested_check, SkillCheckResult, ability_modifier
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

ROLE_PRODUCTION = {
    "blacksmith": ("iron_bar", "iron_sword"),
    "innkeeper": ("bread", "ale"),
    "merchant": ("torch",),
    "priest": ("healing_potion",),
}

# Starter inventory kits per class
STARTER_KITS = {
    "warrior": [
        {"id": "iron_sword", "name": "Iron Sword", "type": "weapon", "damage": 6, "material": "iron", "slot": "weapon"},
        {"id": "chain_mail", "name": "Chain Mail", "type": "armor", "ac_bonus": 4, "material": "iron", "slot": "armor"},
        {"id": "torch", "name": "Torch", "type": "tool", "uses": 10},
        {"id": "bread", "name": "Bread", "type": "consumable", "heal": 3, "qty": 3},
    ],
    "rogue": [
        {"id": "daggers", "name": "Twin Daggers", "type": "weapon", "damage": 4, "material": "iron", "slot": "weapon"},
        {"id": "leather_armor", "name": "Leather Armor", "type": "armor", "ac_bonus": 2, "material": "leather", "slot": "armor"},
        {"id": "lockpick", "name": "Lockpick Set", "type": "tool", "uses": 5},
        {"id": "rope", "name": "Rope (50ft)", "type": "tool"},
        {"id": "bread", "name": "Bread", "type": "consumable", "heal": 3, "qty": 2},
    ],
    "mage": [
        {"id": "staff", "name": "Oak Staff", "type": "weapon", "damage": 3, "material": "wood", "slot": "weapon"},
        {"id": "robes", "name": "Mystic Robes", "type": "armor", "ac_bonus": 1, "material": "cloth", "slot": "armor"},
        {"id": "mana_potion", "name": "Mana Potion", "type": "consumable", "restore_sp": 6, "qty": 2},
        {"id": "scroll_fireball", "name": "Scroll of Fireball", "type": "scroll", "spell": "fireball"},
    ],
    "priest": [
        {"id": "mace", "name": "Iron Mace", "type": "weapon", "damage": 5, "material": "iron", "slot": "weapon"},
        {"id": "robes", "name": "Holy Robes", "type": "armor", "ac_bonus": 1, "material": "cloth", "slot": "armor"},
        {"id": "shield", "name": "Wooden Shield", "type": "shield", "ac_bonus": 2, "material": "wood", "slot": "shield"},
        {"id": "healing_potion", "name": "Healing Potion", "type": "consumable", "heal": 8, "qty": 2},
        {"id": "holy_water", "name": "Holy Water", "type": "consumable", "damage_undead": 10},
    ],
}


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


class GameEngine:
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

        stats = class_stats.get(player_class.lower(), class_stats["warrior"])
        hp    = class_hp.get(player_class.lower(), 16)
        sp    = class_sp.get(player_class.lower(), 0)

        player = Character(
            name=player_name,
            classes={player_class.lower(): 1},
            stats=stats,
            hp=hp, max_hp=hp,
            spell_points=sp, max_spell_points=sp,
            level=1, xp=0,
        )

        if location is None:
            loc, _ = random.choice(_OPENING_SCENES)
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
                session.equipment[slot] = item
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
                session.inventory.append(item)

        session.quest_offers = self._generate_emergent_quests(session, force=True)
        session.narration_context["last_world_tick_hour"] = self._current_game_hour(session)
        session.ensure_consistency()
        return session

    def _populate_scene_entities(self, session: GameSession, location: str) -> None:
        """Populate session with NPC Entity objects in the spatial index, plus backward-compat dict."""
        session.entities = {}
        loc_lower = location.lower()
        anchors = self._scene_anchor_positions(session)

        # Define NPC archetypes by location type
        if any(w in loc_lower for w in ["tavern", "inn"]):
            roles = [("innkeeper", "merchant_guild"), ("guard", "harbor_guard"),
                     ("quest_giver", "merchant_guild"), ("beggar", "thieves_guild")]
        elif any(w in loc_lower for w in ["market", "harbor", "town", "city"]):
            roles = [("merchant", "merchant_guild"), ("guard", "harbor_guard"),
                     ("blacksmith", "mountain_dwarves"), ("beggar", "thieves_guild"),
                     ("priest", "temple_order")]
        elif any(w in loc_lower for w in ["forest", "road", "path"]):
            roles = [("spy", "thieves_guild"), ("guard", "harbor_guard")]
        else:
            roles = [("merchant", "merchant_guild"), ("guard", "harbor_guard")]

        for role, faction in roles:
            npc_id = f"{role}_{len(session.entities) + 1}"
            # Pick gender randomly
            gender = random.choice(["male", "female"])
            # Choose faction-appropriate name generation faction
            name_faction = "human"
            if faction == "mountain_dwarves":
                name_faction = "dwarf"
            elif faction == "forest_elves":
                name_faction = "elf"
            name = session.name_gen.generate_name(faction=name_faction, gender=gender, npc_id=npc_id)

            # Find a walkable position near spawn
            pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=5)
            needs = NPCNeeds()

            # Determine glyph/color from NPC_VISUALS
            glyph, color = NPC_VISUALS.get(role, ("?", "white"))
            body = BodyPartTracker()
            schedule_data = DEFAULT_SCHEDULES.get(role, DEFAULT_SCHEDULES["merchant"])
            schedule_positions = {
                period: list(anchors.get(place, pos))
                for period, place in schedule_data.items()
            }
            patrol_route = None
            if role == "guard":
                patrol_route = [
                    list(anchors.get("gate", pos)),
                    list(anchors.get("market_square", pos)),
                    list(anchors.get("tavern", pos)),
                    list(anchors.get("gate", pos)),
                ]
            schedule = NPCSchedule(
                npc_id=npc_id,
                npc_name=name,
                locations=dict(schedule_data),
                positions=schedule_positions,
                patrol_route=patrol_route,
            )

            # Build NPC skills based on role
            npc_skills = {}
            if role == "guard":
                npc_skills = {"melee": 3, "patrol": 2}
            elif role == "merchant":
                npc_skills = {"trade": 4, "appraisal": 3}
            elif role == "blacksmith":
                npc_skills = {"smithing": 5, "trade": 2}
            elif role == "innkeeper":
                npc_skills = {"trade": 3, "cooking": 4}
            elif role == "healer":
                npc_skills = {"healing": 5, "herbalism": 3}
            elif role == "priest":
                npc_skills = {"healing": 3, "divine_magic": 4}

            # Create proper Entity object
            entity = Entity(
                id=npc_id,
                entity_type=EntityType.NPC,
                name=name,
                position=tuple(pos),
                glyph=glyph,
                color=color,
                blocking=True,
                needs=needs,
                skills=npc_skills if npc_skills else None,
                body=body,
                faction=faction,
                schedule=schedule,
                job=role,
                disposition="friendly" if role != "spy" else "neutral",
                hp=12 if role == "guard" else 8,
                max_hp=12 if role == "guard" else 8,
            )

            # Add to spatial index
            if session.spatial_index is not None:
                session.spatial_index.add(entity)

            # Backward-compatible dict representation in session.entities
            session.entities[npc_id] = {
                "name": name,
                "type": "npc",
                "position": list(pos),
                "faction": faction,
                "role": role,
                "needs": needs,
                "body": body,
                "schedule": schedule,
                "gender": gender,
                "entity_ref": entity,  # reference to the Entity object
            }

        self._spawn_workstations(session, anchors)

    def _find_walkable_near(self, session: GameSession, cx: int, cy: int, radius: int = 5) -> list:
        """Find a walkable tile near (cx, cy) using map_data. Falls back to random offset."""
        if session.map_data is not None:
            # Try positions in expanding rings
            for r in range(1, radius + 1):
                candidates = []
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if abs(dx) != r and abs(dy) != r:
                            continue  # only ring edges
                        nx, ny = cx + dx, cy + dy
                        if session.map_data.is_walkable(nx, ny):
                            if session.spatial_index is None or not session.spatial_index.blocking_at(nx, ny):
                                candidates.append([nx, ny])
                if candidates:
                    return random.choice(candidates)
        # Fallback: random offset
        return [cx + random.randint(-2, 2), cy + random.randint(-2, 2)]

    def _scene_anchor_positions(self, session: GameSession) -> Dict[str, List[int]]:
        if not session.map_data:
            px, py = session.position[0], session.position[1]
            return {name: [px, py] for name in {
                "home", "shop", "market_square", "tavern", "gate",
                "forge", "temple", "alley", "docks", "campfire",
            }}

        spawn_x, spawn_y = session.map_data.spawn_point
        offsets = {
            "home": (-6, -3),
            "shop": (5, -1),
            "market_square": (0, 4),
            "tavern": (6, 5),
            "gate": (0, -7),
            "forge": (8, 1),
            "temple": (-8, 1),
            "alley": (-6, 5),
            "docks": (9, 6),
            "campfire": (-4, 7),
        }
        anchors: Dict[str, List[int]] = {}
        for name, (dx, dy) in offsets.items():
            anchors[name] = self._find_walkable_near(session, spawn_x + dx, spawn_y + dy, radius=4)
        return anchors

    def _spawn_workstations(self, session: GameSession, anchors: Dict[str, List[int]]) -> None:
        if session.spatial_index is None:
            return
        existing = {entity.id for entity in session.spatial_index.all_entities()}
        for workstation_id, spec in WORKSTATION_SPECS.items():
            entity_id = f"workstation_{workstation_id}"
            if entity_id in existing:
                continue
            anchor_name = WORKSTATION_ANCHORS.get(workstation_id, "shop")
            pos = anchors.get(anchor_name, list(session.position))
            entity = Entity(
                id=entity_id,
                entity_type=EntityType.FURNITURE,
                name=spec["name"],
                position=tuple(pos),
                glyph=spec["glyph"],
                color=spec["color"],
                blocking=False,
                inventory=[{"workstation": workstation_id}],
            )
            session.spatial_index.add(entity)

    def _current_game_hour(self, session: GameSession) -> float:
        if not getattr(session, "game_time", None):
            return 0.0
        return ((session.game_time.day - 1) * 24) + session.game_time.hour + (session.game_time.minute / 60.0)

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

        session.touch()
        session.dm_context.advance_turn()

        handlers = {
            ActionIntent.ATTACK:     self._handle_attack,
            ActionIntent.CAST_SPELL: self._handle_spell,
            ActionIntent.USE_ITEM:   self._handle_use_item,
            ActionIntent.EXAMINE:    self._handle_examine,
            ActionIntent.LOOK:       self._handle_look,
            ActionIntent.TALK:       self._handle_talk,
            ActionIntent.REST:       self._handle_rest,
            ActionIntent.MOVE:       self._handle_move,
            ActionIntent.OPEN:       self._handle_open,
            ActionIntent.TRADE:      self._handle_trade,
            ActionIntent.FLEE:       self._handle_flee,
            ActionIntent.INVENTORY:  self._handle_inventory,
            ActionIntent.PICKUP:     self._handle_pickup,
            ActionIntent.PICK_UP:    self._handle_pickup,
            ActionIntent.DROP:       self._handle_drop,
            ActionIntent.EQUIP:      self._handle_equip,
            ActionIntent.UNEQUIP:    self._handle_unequip,
            ActionIntent.CRAFT:      self._handle_craft,
            ActionIntent.SEARCH:     self._handle_search,
            ActionIntent.STEAL:      self._handle_steal,
            ActionIntent.PERSUADE:   self._handle_persuade,
            ActionIntent.INTIMIDATE: self._handle_intimidate,
            ActionIntent.SNEAK:      self._handle_sneak,
            ActionIntent.CLIMB:      self._handle_climb,
            ActionIntent.LOCKPICK:   self._handle_lockpick,
            ActionIntent.PRAY:       self._handle_pray,
            ActionIntent.READ_ITEM:  self._handle_read_item,
            ActionIntent.PUSH:       self._handle_push,
            ActionIntent.FISH:       self._handle_fish,
            ActionIntent.MINE:       self._handle_mine,
            ActionIntent.CHOP:       self._handle_chop,
            ActionIntent.UNKNOWN:    self._handle_unknown,
        }

        handler = handlers.get(action.intent, self._handle_unknown)
        result = handler(session, action)

        world_minutes = int(result.state_changes.pop("_world_minutes", 15)) if result.state_changes else 15
        skip_world_tick = bool(result.state_changes.pop("_skip_world_tick", False)) if result.state_changes else False

        if not skip_world_tick:
            world_events = self._world_tick(session, minutes=world_minutes, refresh_ap=(action.intent == ActionIntent.REST))
            self._merge_world_events(session, result, world_events)

        session.sync_player_state()
        return result

    # --- Intent Handlers ---

    def _handle_attack(self, session: GameSession, action: ParsedAction) -> ActionResult:
        # Proximity check for attack (melee range)
        if action.target:
            prox_fail = self._check_entity_proximity(session, action.target, "attack_melee")
            if prox_fail:
                return prox_fail

        # --- Bug 1: Non-hostile target handling (route to DM for funny response) ---
        hostile_keywords = ["goblin", "orc", "bandit", "wolf", "skeleton", "zombie",
                            "enemy", "monster", "troll", "guard", "militia", "watchman",
                            "ogre", "dragon", "rat", "spider", "cultist", "thug"]
        target_lower = (action.target or "").lower()
        in_active_combat = session.dm_context.scene_type == SceneType.COMBAT
        found_world_target = self._find_entity_by_name(session, action.target) if action.target else None

        if not in_active_combat and found_world_target is not None:
            world_target_id, world_target = found_world_target
            enemy = self._character_from_world_entity(world_target_id, world_target)
            if enemy is not None:
                self._start_combat(session, [enemy])
                combat = session.combat
                target_idx = self._find_target(combat, enemy.name, exclude=session.player.name)
                if target_idx is not None:
                    return self._execute_attack_round(session, combat, target_idx)

        if not in_active_combat and action.target and found_world_target is None and not any(kw in target_lower for kw in hostile_keywords):
            # Non-hostile target → creative DM response
            target_name = action.target or "something"
            desc = (
                f"The player tries to attack '{target_name}' which is not a hostile creature. "
                f"As DM, react humorously or creatively to this absurd action. "
                f"Maybe the {target_name} 'fights back' in an absurd way, "
                f"maybe NPCs nearby react with laughter or alarm, or maybe something funny happens."
            )
            event = DMEvent(
                type=EventType.EXPLORATION,
                description=desc,
                data={
                    "raw_input": action.raw_input,
                    "target": action.target,
                    "action": "attack_nonhostile",
                },
            )
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
            return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

        # --- Bug 4: If already in combat, target existing enemy instead of spawning new ---
        if session.in_combat() and session.combat:
            combat = session.combat
            # Use _find_target to support both existing and specified targets
            target_idx = self._find_target(combat, action.target, exclude=session.player.name)
            if target_idx is None:
                return ActionResult(
                    narrative="No valid target found.",
                    scene_type=session.dm_context.scene_type,
                )
            return self._execute_attack_round(session, combat, target_idx)

        # Not in combat — start new combat
        if not session.in_combat():
            enemy = self._spawn_enemy(session.player.level)
            self._start_combat(session, [enemy])

        combat = session.combat
        target_idx = self._find_target(combat, action.target, exclude=session.player.name)

        if target_idx is None:
            return ActionResult(
                narrative="No valid target found.",
                scene_type=session.dm_context.scene_type,
            )

        return self._execute_attack_round(session, combat, target_idx)

    def _build_combat_narrative(self, session, attacker_name, target, hit, damage, crit=False, fumble=False):
        """Generate LLM narrative for a player attack. Falls back to template on failure."""
        # Template fallback strings
        if crit:
            fallback = f"CRITICAL! {attacker_name} lands a devastating blow — {damage} damage!"
        elif fumble:
            fallback = f"{attacker_name} stumbles — the attack goes wide!"
        elif hit:
            fallback = f"{attacker_name} strikes — hit! {damage} damage."
        else:
            fallback = f"{attacker_name} swings but misses."
        if self.llm is None:
            return fallback
        try:
            if hit:
                desc = (
                    f"{attacker_name} attacks {target.name}. "
                    f"{'Critical hit! ' if crit else ''}Dealt {damage} damage. "
                    f"{target.name} has {target.hp} HP remaining. "
                    f"Describe the attack {'critically ' if crit else ''}hitting cinematically in 1-2 sentences."
                )
            else:
                desc = (
                    f"{attacker_name} attacks {target.name} but {'fumbles and ' if fumble else ''}misses. "
                    f"Describe the miss dramatically in 1 sentence."
                )
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "player_name": session.player.name,
                "target_name": target.name,
                "hit": hit,
                "damage": damage,
                "player_hp": session.player.hp,
                "player_max_hp": session.player.max_hp,
                "target_hp": target.hp,
                "action": "attack",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_enemy_combat_narrative(self, session, enemy, hit, damage):
        """Generate LLM narrative for an enemy counterattack. Falls back to template on failure."""
        if hit:
            fallback = f"{enemy.name} hits you for {damage} damage! (HP: {session.player.hp}/{session.player.max_hp})"
        else:
            fallback = f"{enemy.name} swings at you but misses!"
        if self.llm is None:
            return fallback
        try:
            desc = (
                f"{enemy.name} counterattacks {session.player.name}. "
                f"{'Hit for ' + str(damage) + ' damage' if hit else 'Miss'}. "
                f"Player has {session.player.hp}/{session.player.max_hp} HP. "
                f"Describe in 1 sentence."
            )
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "attacker_name": enemy.name,
                "player_name": session.player.name,
                "hit": hit,
                "damage": damage,
                "player_hp": session.player.hp,
                "player_max_hp": session.player.max_hp,
                "action": "enemy_attack",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_death_narrative(self, session, enemy_name):
        """Generate LLM narrative for enemy death. Falls back to template on failure."""
        fallback = f"{enemy_name} has been defeated!"
        if self.llm is None:
            return fallback
        try:
            desc = f"{enemy_name} has been defeated! Describe their death dramatically in 1-2 sentences."
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "enemy_name": enemy_name,
                "action": "enemy_death",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _execute_attack_round(self, session: GameSession, combat: CombatManager, target_idx: int) -> ActionResult:
        """Execute player's attack and then all living enemy counterattacks."""
        weapon = self._build_weapon_item(session.equipment.get("weapon"))
        try:
            result = combat.attack(target_idx, weapon=weapon) if weapon else combat.attack(target_idx)
        except TypeError:
            result = combat.attack(target_idx)
        state_changes = {}
        narrative_parts = []

        # Identify target for narrative
        target_combatant = None
        if 0 <= target_idx < len(combat.combatants):
            target_combatant = combat.combatants[target_idx]

        hit = result.get("hit", False)
        raw_damage = result.get("damage", 0)
        damage = raw_damage
        crit = result.get("crit", False)
        fumble = result.get("fumble", False)

        # --- Body part + material system ---
        hit_part = None
        armor_reduction = 0
        material_bonus = ""
        if hit or crit:
            # Roll hit location
            hit_part = roll_hit_location()
            equipped_armor = getattr(target_combatant.character, 'equipped_armor', []) if target_combatant else []
            armor_reduction = calculate_armor_reduction(hit_part, equipped_armor)
            # Apply weapon material bonus (default iron)
            weapon_material = getattr(session.player, 'weapon_material', 'iron')
            if weapon_material in MATERIALS:
                mat = MATERIALS[weapon_material]
                damage = max(1, int(raw_damage * mat.damage_mult))
                material_bonus = f" ({weapon_material})"
            # Reduce damage by armor
            effective_damage = max(0, damage - armor_reduction)
            if target_combatant is not None:
                corrected_hp = target_combatant.character.hp + raw_damage - effective_damage
                target_combatant.character.hp = max(0, min(target_combatant.character.max_hp, corrected_hp))
                if target_combatant.character.hp <= 0:
                    target_combatant.is_dead = True
                    result["killed"] = True
                else:
                    target_combatant.is_dead = False
                    result["killed"] = False
                entity_id = getattr(target_combatant.character, "_entity_id", None)
                if entity_id and entity_id in session.entities:
                    session.entities[entity_id]["hp"] = target_combatant.character.hp
                    session.entities[entity_id]["alive"] = not target_combatant.is_dead
                    entity_ref = session.entities[entity_id].get("entity_ref")
                    if entity_ref is not None:
                        entity_ref.hp = target_combatant.character.hp
                        entity_ref.alive = not target_combatant.is_dead
                        entity_ref.blocking = not target_combatant.is_dead
            # Apply body part damage to tracker (for the target if it's an enemy)
            state_changes["hit_location"] = hit_part
            state_changes["armor_reduction"] = armor_reduction
            state_changes["effective_damage"] = effective_damage
            # Update the result damage
            result["damage"] = effective_damage
            damage = effective_damage

        if target_combatant:
            hit_part_str = f" in the {hit_part}" if hit_part else ""
            narrative_parts.append(
                self._build_combat_narrative(
                    session, session.player.name, target_combatant.character,
                    hit=hit or crit, damage=damage, crit=crit, fumble=fumble
                )
            )
            if hit_part and (hit or crit):
                armor_str = f" (armor absorbed {armor_reduction})" if armor_reduction > 0 else ""
                narrative_parts.append(f"[Hit: {hit_part}{material_bonus}{armor_str}]")
        else:
            # Fallback if no target
            if crit:
                narrative_parts.append(f"CRITICAL! {session.player.name} lands a devastating blow — {damage} damage!")
            elif fumble:
                narrative_parts.append(f"{session.player.name} stumbles — the attack goes wide!")
            elif hit:
                narrative_parts.append(f"{session.player.name} strikes — hit! {damage} damage.")
            else:
                narrative_parts.append(f"{session.player.name} swings but misses.")

        # --- Bug 5: Guard backup in town ---
        if result.get("killed"):
            target_name = result.get("target", "")
            narrative_parts.append(self._build_death_narrative(session, target_name or "the enemy"))
            quest_events = self._update_quest_progress_for_kill(session, target_name or "")
            if quest_events:
                state_changes.setdefault("world_events", []).extend(copy.deepcopy(quest_events))
                for event in quest_events:
                    narrative_parts.append(
                        f"Quest complete: {event.get('title', event.get('quest_id', 'Unknown quest'))}. "
                        f"+{event.get('reward_gold', 0)} gold, +{event.get('reward_xp', 0)} XP."
                    )
            killed_combatant = next(
                (c for c in combat.combatants if c.name == target_name), None
            )
            if killed_combatant:
                killed_char = killed_combatant.character
                role = getattr(killed_char, "role", "")
                location = (session.dm_context.location or "").lower()
                is_town = any(w in location for w in ["town", "village", "city", "square", "market", "tavern", "inn"])
                if is_town and role in ["guard", "militia", "watchman"]:
                    backup1 = self._spawn_guard_backup(session)
                    backup2 = self._spawn_guard_backup(session)
                    combat.combatants.append(
                        __import__("engine.core.combat", fromlist=["Combatant"]).Combatant(
                            character=backup1, initiative=10
                        )
                    )
                    combat.combatants.append(
                        __import__("engine.core.combat", fromlist=["Combatant"]).Combatant(
                            character=backup2, initiative=9
                        )
                    )
                    narrative_parts.append(
                        "Nearby guards heard the commotion! Two more guards rush toward you, weapons drawn!"
                    )

        # --- Bug 2: Enemy counterattack after player's action ---
        if not combat.combat_ended:
            from engine.core.enemy_ai import EnemyAI
            enemy_ai = EnemyAI()
            living_enemies = [
                c for c in combat.combatants
                if not c.is_dead and c.name != session.player.name
            ]
            player_idx = next(
                (i for i, c in enumerate(combat.combatants) if c.name == session.player.name), None
            )
            if player_idx is not None:
                for enemy_combatant in living_enemies:
                    if combat.combat_ended:
                        break
                    # Temporarily set active turn to enemy for attack resolution
                    saved_turn = combat.current_turn
                    combat.current_turn = combat.combatants.index(enemy_combatant)
                    enemy_combatant.ap = 3  # Give enemy AP for this counterattack
                    enemy_result = combat.attack(player_idx)
                    combat.current_turn = saved_turn
                    if enemy_result.get("hit"):
                        raw_enemy_damage = enemy_result.get("damage", 0)
                        # Body part hit location for player damage
                        player_hit_part = roll_hit_location()
                        player_armor = getattr(session.player, 'equipped_armor', [])
                        player_armor_red = calculate_armor_reduction(player_hit_part, player_armor)
                        effective_dmg = max(0, raw_enemy_damage - player_armor_red)
                        # Apply to body part tracker
                        session.body_tracker.apply_damage(player_hit_part, effective_dmg)
                        session.player.hp = max(
                            0,
                            min(session.player.max_hp, session.player.hp + raw_enemy_damage - effective_dmg),
                        )
                        # Sync the combat combatant's hp too
                        player_combatant = combat.combatants[player_idx]
                        player_combatant.character.hp = session.player.hp
                        narrative_parts.append(
                            self._build_enemy_combat_narrative(session, enemy_combatant, hit=True, damage=effective_dmg)
                        )
                        if player_armor_red > 0 or player_hit_part:
                            armor_note = f" (armor absorbed {player_armor_red})" if player_armor_red > 0 else ""
                            narrative_parts.append(f"[Hit your {player_hit_part}{armor_note}]")
                    elif enemy_result.get("fumble") or not enemy_result.get("hit"):
                        narrative_parts.append(
                            self._build_enemy_combat_narrative(session, enemy_combatant, hit=False, damage=0)
                        )

                    if session.player.hp <= 0:
                        narrative_parts.append("You have fallen in combat... darkness closes in.")
                        combat.combat_ended = True
                        break

        narrative_text = " ".join(narrative_parts)
        combat_state = self._combat_state(combat)
        xp_result = None

        if combat.combat_ended:
            xp = XP_REWARDS.get(session.player.level, 100)
            if session.player.hp > 0:
                xp_result = self.progression.add_xp(session.player, xp)
                state_changes["xp_gained"] = xp
                if xp_result:
                    state_changes["level_up"] = xp_result.new_level

            event = DMEvent(
                type=EventType.COMBAT_END,
                description=narrative_text,
                data=combat.get_summary(),
            )
            self.dm.transition(session.dm_context, SceneType.EXPLORATION)
            # For combat end, do a final narrate to wrap up the battle
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
        else:
            # Individual parts are already LLM-narrated; return them directly
            narrative = narrative_text

        return ActionResult(
            narrative=narrative,
            events=[result],
            state_changes=state_changes,
            scene_type=session.dm_context.scene_type,
            combat_state=combat_state,
            level_up=xp_result,
        )

    def _spawn_guard_backup(self, session: GameSession) -> Character:
        """Spawn a backup town guard."""
        guard = Character(
            name="Town Guard",
            hp=12, max_hp=12,
            stats={"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 12},
        )
        guard.role = "guard"
        return guard

    def _handle_spell(self, session: GameSession, action: ParsedAction) -> ActionResult:
        if session.player.spell_points <= 0:
            return ActionResult(
                narrative="Your spell points are exhausted. You need to rest.",
                scene_type=session.dm_context.scene_type,
            )

        from engine.core.spell import Spell, TargetType
        from engine.core.effect import DamageEffect
        spell = Spell(
            name="Magic Missile",
            cost=2,
            range=120,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="2d4+2", damage_type="force")],
        )

        if not session.in_combat():
            enemy = self._spawn_enemy(session.player.level)
            self._start_combat(session, [enemy])

        combat = session.combat
        target_idx = self._find_target(combat, action.target, exclude=session.player.name)
        if target_idx is None:
            return ActionResult(
                narrative="No valid target for the spell.",
                scene_type=session.dm_context.scene_type,
            )

        result = combat.cast_spell(spell, target_idx)

        if "error" in result:
            # Spell failed — return error narrative directly, skip LLM
            return ActionResult(
                narrative=f"The spell failed: {result['error']}",
                events=[result],
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(combat),
            )

        desc = f"{session.player.name} unleashes {spell.name}!"
        fallback_narrative = f"{session.player.name} unleashes {spell.name} with a surge of magical force!"

        event = DMEvent(type=EventType.ENCOUNTER, description=desc, data={
            "player_name": session.player.name,
            "spell_name": spell.name,
            "action": "cast_spell",
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        # If LLM returned a generic template without spell keywords, use specific fallback
        spell_keywords = ["spell", "magic", "missile", "force", "unleash", "cast", "arcane", "incantation", "surge"]
        if not any(kw in narrative.lower() for kw in spell_keywords):
            narrative = fallback_narrative

        return ActionResult(
            narrative=narrative,
            events=[result],
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(combat),
        )

    def _handle_look(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Handle 'look around', 'look', 'observe' — scene description at current location."""
        # --- Bug 3: Combat look shows combat status ---
        if session.dm_context.scene_type == SceneType.COMBAT and session.combat:
            enemies = [c for c in session.combat.combatants if not c.is_dead and c.name != session.player.name]
            enemy_desc = ", ".join([f"{e.name} (HP:{e.character.hp})" for e in enemies])
            narrative = (
                f"You're in combat! Enemies: {enemy_desc}. "
                f"Player HP: {session.player.hp}/{session.player.max_hp}"
            )
            return ActionResult(narrative=narrative, scene_type=SceneType.COMBAT)

        location = session.dm_context.location or "the area"
        world_context = self._build_world_context(session)
        desc = (
            f"{session.player.name} surveys their surroundings in {location}. "
            f"Current location: {location}. "
            f"They take in the sights, sounds, and atmosphere of {location} specifically.\n"
            f"{world_context}"
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name,
            "location": location,
            "current_location": location,
            "action": "look around",
            "world_context": world_context,
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_examine(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or session.dm_context.location

        # Proximity check for examining entities
        prox_fail = self._check_entity_proximity(session, target, "examine")
        if prox_fail:
            return prox_fail

        world_context = self._build_world_context(session)
        desc = f"{session.player.name} examines {target} closely, looking for details.\n{world_context}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "action": f"examine {target}",
            "target": target,
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_talk(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or "a stranger"

        # Proximity check
        prox_fail = self._check_entity_proximity(session, target, "talk")
        if prox_fail:
            return prox_fail

        # Try to find NPC personality from templates
        npc_personality = self._get_npc_personality(target)

        # Check NPC memory for prior interactions
        npc_id = target.lower().replace(" ", "_")
        memory = session.npc_memory.get_memory(npc_id, npc_name=target)
        prior_context = {}
        if memory and len(memory.conversations) > 0:
            prior_context["prior_interactions"] = len(memory.conversations)
            prior_context["npc_memory_summary"] = memory.build_context()

        # Check NPC willingness to talk (from needs system)
        found_entity = self._find_entity_by_name(session, target)
        npc_mood = "content"
        npc_behavior = {}
        accepted_quest_note = ""
        if found_entity:
            _, entity = found_entity
            needs = entity.get("needs")
            if isinstance(needs, NPCNeeds):
                npc_mood = needs.emotional_state()
                npc_behavior = needs.behavior_modifiers()
                if not npc_behavior.get("will_talk", True):
                    return ActionResult(
                        narrative=f"{entity['name']} looks too anxious to talk right now. Their eyes dart around nervously.",
                        scene_type=session.dm_context.scene_type,
                    )
            if entity.get("role") in {"quest_giver", "guard", "merchant"} and session.quest_offers:
                accepted = self._accept_quest_offer(session, session.quest_offers[0])
                if accepted:
                    accepted_quest_note = f"\nQuest accepted: {session.quest_offers[0]['title']}."
                    session.quest_offers = [offer for offer in session.quest_offers if offer.get("id") != accepted]

        world_context = self._build_world_context(session)
        desc = (
            f"{session.player.name} approaches {target} to speak. "
            f"{session.player.name} says: (initiate conversation). "
            f"Generate {target}'s response as they would actually speak, "
            f"in character with their personality.\n"
            f"NPC mood: {npc_mood}.\n"
            f"{world_context}"
        )
        event_data = {
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "npc_name": target,
            "npc_personality": npc_personality,
            "npc_mood": npc_mood,
            "action": "talk",
            "player_input": action.raw_input,
            "world_context": world_context,
        }
        event_data.update(prior_context)

        event = DMEvent(type=EventType.DIALOGUE, description=desc, data=event_data)
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)

        # Record this interaction
        from datetime import datetime
        game_time = datetime.now().strftime("%Y-%m-%d")
        session.npc_memory.record_interaction(
            npc_id,
            action.raw_input[:200],
            "neutral",
            session.game_time.to_string() if session.game_time else game_time,
        )

        return ActionResult(narrative=f"{narrative}{accepted_quest_note}", scene_type=session.dm_context.scene_type)

    def _get_npc_personality(self, target_name: str) -> dict:
        """Find NPC template by partial name match."""
        try:
            import json, os
            data_dir = os.path.join(os.path.dirname(__file__), "../../data")
            with open(os.path.join(data_dir, "npc_templates.json")) as f:
                npcs = json.load(f)["npc_templates"]
            target_lower = target_name.lower()
            for npc in npcs:
                if (target_lower in npc.get("name", "").lower() or
                    target_lower in npc.get("id", "").lower() or
                    target_lower in npc.get("role", "").lower()):
                    return {
                        "name": npc.get("name"),
                        "role": npc.get("role"),
                        "personality": npc.get("personality", []),
                        "speech_style": npc.get("speech_style"),
                        "greeting": npc.get("dialogue", {}).get("greeting", []),
                    }
        except Exception:
            pass
        return {}

    def _handle_rest(self, session: GameSession, action: ParsedAction) -> ActionResult:
        if session.in_combat():
            return ActionResult(
                narrative="You cannot rest in the middle of a fight!",
                scene_type=session.dm_context.scene_type,
            )

        heal = max(1, session.player.max_hp // 4)
        session.player.hp = min(session.player.hp + heal, session.player.max_hp)
        session.player.spell_points = session.player.max_spell_points
        # Heal body parts during rest
        for part in session.body_tracker.current_hp:
            session.body_tracker.heal(part, max(1, session.body_tracker.max_hp[part] // 4))

        desc = f"{session.player.name} takes a short rest and recovers {heal} HP."
        event = DMEvent(type=EventType.REST, description=desc)
        self.dm.transition(session.dm_context, SceneType.REST)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)

        return ActionResult(
            narrative=narrative,
            state_changes={"hp_restored": heal, "_world_minutes": 480},
            scene_type=session.dm_context.scene_type,
        )

    def _handle_move(self, session: GameSession, action: ParsedAction) -> ActionResult:
        # --- Bug 3: Block movement during combat, allow flee ---
        if session.dm_context.scene_type == SceneType.COMBAT:
            flee_words = ["flee", "run", "escape", "retreat"]
            if action.raw_input and any(w in action.raw_input.lower() for w in flee_words):
                return self._handle_flee(session, action)
            return ActionResult(
                narrative="You can't simply walk away — you're in the middle of combat! Fight, cast a spell, or flee if you must.",
                scene_type=SceneType.COMBAT,
            )

        dest = action.direction or action.target or action.action_detail or "forward"
        # Clean direction strings like "to the tavern" -> "the tavern"
        if dest and dest.startswith("to "):
            dest = dest[3:]

        DIRECTION_DELTAS = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
        }
        has_map = session.map_data is not None
        MAP_SIZE = session.map_data.width if has_map else 32
        MAP_H = session.map_data.height if has_map else 32
        dest_lower = dest.lower()

        moved = False
        blocked_msg = None

        if dest_lower in ("left", "right"):
            # Turn only, don't move
            turn_map = {
                "left":  {"north": "west", "west": "south", "south": "east", "east": "north"},
                "right": {"north": "east", "east": "south", "south": "west", "west": "north"},
            }
            session.facing = turn_map[dest_lower].get(session.facing, session.facing)
        elif dest_lower in DIRECTION_DELTAS:
            session.facing = dest_lower
            dx, dy = DIRECTION_DELTAS[dest_lower]
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            # Clamp to map bounds
            new_x = max(0, min(MAP_SIZE - 1, new_x))
            new_y = max(0, min(MAP_H - 1, new_y))

            # Check walkability via map_data
            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            # Check blocking entities via spatial_index
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blockers = session.spatial_index.at(new_x, new_y)
                blocker_names = [e.name for e in blockers if e.blocking and e.id != "player"]
                if blocker_names:
                    blocked_msg = f"{blocker_names[0]} is blocking the way."
                else:
                    blocked_msg = "Something blocks your path."
            else:
                # Check AP cost
                move_cost = ACTION_COSTS.get("move_flat", 1)
                if session.ap_tracker and not session.ap_tracker.can_move(move_cost):
                    blocked_msg = f"Not enough action points to move. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})"
                else:
                    # Spend AP
                    if session.ap_tracker:
                        session.ap_tracker.spend_movement(move_cost)
                    # Move player in spatial index
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
        elif dest_lower == "forward":
            dx, dy = DIRECTION_DELTAS.get(session.facing, (0, -1))
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            new_x = max(0, min(MAP_SIZE - 1, new_x))
            new_y = max(0, min(MAP_H - 1, new_y))

            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blocked_msg = "Something blocks your path."
            else:
                if session.ap_tracker:
                    if not session.ap_tracker.spend_movement(ACTION_COSTS.get("move_flat", 1)):
                        blocked_msg = "Not enough action points to move."
                    else:
                        if session.spatial_index and session.player_entity:
                            session.spatial_index.move(session.player_entity, new_x, new_y)
                        session.position = [new_x, new_y]
                        moved = True
                else:
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
        else:
            # Named destination or coordinate
            import re
            coord_match = re.match(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$", str(dest))
            if coord_match:
                try:
                    x = int(coord_match.group(1))
                    y = int(coord_match.group(2))
                    x = max(0, min(MAP_SIZE - 1, x))
                    y = max(0, min(MAP_H - 1, y))
                    if has_map and not session.map_data.is_walkable(x, y):
                        blocked_msg = "That position is not walkable."
                    else:
                        if session.spatial_index and session.player_entity:
                            session.spatial_index.move(session.player_entity, x, y)
                        session.position = [x, y]
                        moved = True
                except Exception:
                    pass
            else:
                # Named destination — just update location name
                session.dm_context.location = dest

        if blocked_msg:
            return ActionResult(narrative=blocked_msg, scene_type=session.dm_context.scene_type)

        # Recompute FOV and center viewport after movement
        if moved and session.viewport and has_map:
            session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0], session.position[1],
                radius=8,
            )

        # Check for hostile entities in visible range -> report them
        hostile_alert = ""
        if moved and session.spatial_index and session.viewport:
            nearby = session.spatial_index.in_radius(session.position[0], session.position[1], 5)
            hostiles = [e for e in nearby if e.is_hostile() and e.is_alive() and e.id != "player"]
            if hostiles:
                names = ", ".join(e.name for e in hostiles)
                hostile_alert = f" You spot hostile creatures nearby: {names}!"

        world_context = self._build_world_context(session)
        desc = f"{session.player.name} moves toward {dest}.\n{world_context}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name,
            "location": dest,
            "action": f"move to {dest}",
            "world_context": world_context,
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        if hostile_alert:
            narrative += hostile_alert

        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
            state_changes={"position": list(session.position)} if moved else {},
        )

    def _handle_flee(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Handle fleeing from combat."""
        if session.combat:
            session.combat.combat_ended = True
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        desc = f"{session.player.name} turns and flees from combat!"
        event = DMEvent(type=EventType.EXPLORATION, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_open(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or "the door"
        desc = f"{session.player.name} tries to open {target}."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_use_item(self, session: GameSession, action: ParsedAction) -> ActionResult:
        desc = f"{session.player.name} reaches for an item."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_trade(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or "a merchant"

        # Proximity check
        prox_fail = self._check_entity_proximity(session, target, "trade")
        if prox_fail:
            return prox_fail

        # Check NPC willingness to trade (from needs)
        found_entity = self._find_entity_by_name(session, target)
        if found_entity:
            _, entity = found_entity
            needs = entity.get("needs")
            if isinstance(needs, NPCNeeds):
                behavior = needs.behavior_modifiers()
                if not behavior.get("will_trade", True):
                    return ActionResult(
                        narrative=f"{entity['name']} shakes their head. 'Not now. Too dangerous to do business.'",
                        scene_type=session.dm_context.scene_type,
                    )

        npc_personality = self._get_npc_personality(target)

        # Build price context from economy
        price_info = []
        for item in ["food", "ale", "iron_bar", "healing_potion", "bread"]:
            stock = session.location_stock.get_stock(item)
            price = session.location_stock.get_effective_price(item)
            if stock > 0:
                price_info.append(f"{item}: {stock} in stock, {price:.1f}g each")
        stock_str = "; ".join(price_info) if price_info else "Limited stock available"

        world_context = self._build_world_context(session)
        desc = (
            f"{session.player.name} wants to trade with {target}. "
            f"Generate {target}'s response showing their wares and willingness to trade.\n"
            f"Available stock: {stock_str}\n"
            f"{world_context}"
        )
        event = DMEvent(type=EventType.DIALOGUE, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "npc_name": target,
            "npc_personality": npc_personality,
            "action": "trade",
            "player_input": action.raw_input,
            "stock_info": stock_str,
            "world_context": world_context,
        })
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_unknown(self, session: GameSession, action: ParsedAction) -> ActionResult:
        # Unknown intent → pass raw input to LLM as free-form DM action
        desc = (
            f"The player says or does: '{action.raw_input}'. "
            f"They are in {session.dm_context.location}. "
            f"As the Dungeon Master, interpret this action and respond narratively. "
            f"If unclear, make a reasonable creative interpretation."
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "raw_input": action.raw_input,
            "action": "free_form",
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    # --- Inventory / Equipment Handlers ---

    def _handle_inventory(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Show the player's inventory and equipped items."""
        lines = []

        # Equipment
        equipped_items = {slot: item for slot, item in session.equipment.items() if item is not None}
        if equipped_items:
            lines.append("== Equipped ==")
            for slot, item in equipped_items.items():
                extra = ""
                if item.get("damage"):
                    extra += f" (dmg: {item['damage']})"
                if item.get("ac_bonus"):
                    extra += f" (AC+{item['ac_bonus']})"
                lines.append(f"  [{slot}] {item['name']}{extra}")

        # Inventory
        if session.inventory:
            lines.append("== Backpack ==")
            for i, item in enumerate(session.inventory):
                qty = item.get("qty", 1)
                qty_str = f" x{qty}" if qty > 1 else ""
                lines.append(f"  {i+1}. {item['name']}{qty_str}")
        elif not equipped_items:
            lines.append("Your inventory is empty.")

        # AP status
        if session.ap_tracker:
            lines.append(f"\nAP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        return ActionResult(
            narrative="\n".join(lines),
            scene_type=session.dm_context.scene_type,
        )

    def _handle_pickup(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Pick up an item entity at the player's position."""
        target = action.target or ""
        px, py = session.position[0], session.position[1]

        # Check AP
        if session.ap_tracker:
            cost = ACTION_COSTS.get("pick_up", 1)
            if not session.ap_tracker.spend(cost):
                return ActionResult(
                    narrative=f"Not enough AP to pick up items. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})",
                    scene_type=session.dm_context.scene_type,
                )

        # Search spatial index for item entities at player position
        if session.spatial_index:
            entities_here = session.spatial_index.at(px, py)
            items_here = [e for e in entities_here if e.entity_type == EntityType.ITEM]
            if target:
                target_lower = target.lower()
                match = next((e for e in items_here if target_lower in e.name.lower()), None)
            else:
                match = items_here[0] if items_here else None

            if match:
                # Remove from spatial index and add to inventory
                session.spatial_index.remove(match)
                item_dict = {"id": match.id, "name": match.name, "type": "item", "entity_id": match.id}
                if match.inventory:
                    item_dict.update(copy.deepcopy(match.inventory[0]))
                item_dict["ground_instance_id"] = match.id
                session.add_item(item_dict, merge=False)
                return ActionResult(
                    narrative=f"You pick up {match.name}.",
                    scene_type=session.dm_context.scene_type,
                )

        return ActionResult(
            narrative=f"There's nothing to pick up here{' matching that name' if target else ''}.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_drop(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Drop an item from inventory onto the ground."""
        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Drop what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        # Search inventory
        match_idx = None
        for i, item in enumerate(session.inventory):
            if target in item.get("name", "").lower() or target in item.get("id", "").lower():
                match_idx = i
                break

        if match_idx is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )

        item = session.remove_item(target)
        if item is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        px, py = session.position[0], session.position[1]

        # Create an item Entity at the player's position
        item_entity = Entity(
            id=item.get("ground_instance_id") or item.get("instance_id") or Entity.generate_id(),
            entity_type=EntityType.ITEM,
            name=item.get("name", "Unknown Item"),
            position=(px, py),
            glyph="!",
            color="yellow",
            blocking=False,
            inventory=[copy.deepcopy(item)],
        )
        if session.spatial_index:
            session.spatial_index.add(item_entity)

        return ActionResult(
            narrative=f"You drop {item['name']} on the ground.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_equip(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Equip an item from inventory, or unequip if target starts with 'un'."""
        raw = (action.raw_input or "").lower()
        target = (action.target or "").lower()

        # Check for unequip intent
        is_unequip = any(w in raw for w in ["unequip", "remove", "take off", "doff"])

        if is_unequip:
            return self._handle_unequip_item(session, target)

        if not target:
            return ActionResult(
                narrative="Equip what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        # Find item in inventory
        match_idx = None
        for i, item in enumerate(session.inventory):
            if target in item.get("name", "").lower() or target in item.get("id", "").lower():
                match_idx = i
                break

        if match_idx is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )

        candidate = session.find_inventory_item(target)
        old_item = session.equipment.get(session._infer_slot(candidate)) if candidate else None
        item = session.equip_item(target)
        if item is None:
            return ActionResult(
                narrative=f"{session.find_inventory_item(target).get('name', target) if session.find_inventory_item(target) else target} cannot be equipped.",
                scene_type=session.dm_context.scene_type,
            )

        narrative = f"You equip {item['name']}."
        if old_item:
            narrative += f" (Unequipped {old_item['name']})"
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_unequip_item(self, session: GameSession, target: str) -> ActionResult:
        """Unequip an item from an equipment slot back to inventory."""
        if not target:
            return ActionResult(
                narrative="Unequip what? Specify an item or slot name.",
                scene_type=session.dm_context.scene_type,
            )

        # Try to match by slot name or item name
        matched_slot = None
        for slot, item in session.equipment.items():
            if item is None:
                continue
            if target in slot or target in item.get("name", "").lower() or target in item.get("id", "").lower():
                matched_slot = slot
                break

        if matched_slot is None:
            return ActionResult(
                narrative=f"Nothing equipped matching '{target}'.",
                scene_type=session.dm_context.scene_type,
            )

        item = session.unequip_item(target)
        if item is None:
            return ActionResult(
                narrative=f"Nothing equipped matching '{target}'.",
                scene_type=session.dm_context.scene_type,
            )

        return ActionResult(
            narrative=f"You unequip {item['name']}.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_craft(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Handle crafting attempts using the CraftingSystem."""
        target = (action.target or "").lower().strip()
        if not target:
            recipe_names = [r.name for r in ALL_RECIPES.values()][:10]
            return ActionResult(
                narrative=f"Craft what? Available recipes: {', '.join(recipe_names)}...",
                scene_type=session.dm_context.scene_type,
            )

        # Find recipe by name match
        recipe: Optional[CraftingRecipe] = None
        for r in ALL_RECIPES.values():
            if target in r.name.lower() or target in r.id.lower():
                recipe = r
                break

        if recipe is None:
            return ActionResult(
                narrative=f"No recipe found for '{target}'. Try 'craft' to see available recipes.",
                scene_type=session.dm_context.scene_type,
            )

        if session.ap_tracker and session.ap_tracker.current_ap <= 0:
            return ActionResult(
                narrative=f"Not enough action points to start crafting. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})",
                scene_type=session.dm_context.scene_type,
            )
        turns_required = 1
        if session.ap_tracker:
            turns_required = max(1, (recipe.ap_cost + session.ap_tracker.max_ap - 1) // session.ap_tracker.max_ap)
            session.ap_tracker.current_ap = 0 if recipe.ap_cost > session.ap_tracker.current_ap else max(0, session.ap_tracker.current_ap - recipe.ap_cost)

        # Check for nearby workstation
        crafting = CraftingSystem()
        workstation_ok = True
        if recipe.workstation != "any" and session.spatial_index:
            ws = crafting.find_nearby_workstation(
                session.spatial_index,
                (session.position[0], session.position[1]),
                recipe.workstation,
            )
            workstation_ok = ws is not None

        # Build inventory dict from session.inventory list
        inv_dict: dict = {}
        for item in session.inventory:
            item_id = item.get("id", item.get("name", "unknown")).lower().replace(" ", "_")
            inv_dict[item_id] = inv_dict.get(item_id, 0) + item.get("qty", 1)
        inventory_before = dict(inv_dict)

        # Map crafting skill to ability
        skill_ability_map = {
            "smithing": "MIG", "alchemy": "MND", "cooking": "INS",
            "carpentry": "AGI", "leatherworking": "AGI",
        }
        ability = skill_ability_map.get(recipe.skill, "MND")
        ability_score = self._get_player_ability(session, ability)

        # Roll skill check
        check_result = roll_check(ability_score, recipe.skill_dc)
        check_text = self._format_skill_check(check_result, ability, recipe.skill_dc)

        # Attempt craft
        craft_result = crafting.attempt_craft(
            roll=check_result.total,
            recipe=recipe,
            inventory=inv_dict,
            workstation_ok=workstation_ok,
        )

        if craft_result.success or craft_result.quality.value == "ruined":
            for item_id, before_qty in inventory_before.items():
                delta = before_qty - inv_dict.get(item_id, 0)
                if delta > 0:
                    session.remove_item(item_id, delta)

            crafted_material = None
            for ingredient in recipe.ingredients:
                ingredient_item = session.find_inventory_item(ingredient.item_id)
                if ingredient_item and ingredient_item.get("material"):
                    crafted_material = ingredient_item.get("material")
                    break
                if any(token in ingredient.item_id for token in ("iron", "steel", "leather", "cloth", "wood")):
                    crafted_material = ingredient.item_id.split("_")[0]
                    break

            for product_id, qty in craft_result.products:
                product_record = {
                    "id": product_id,
                    "name": product_id.replace("_", " ").title(),
                    "qty": qty,
                    "quality": craft_result.quality.value,
                }
                if crafted_material:
                    product_record["material"] = crafted_material
                session.add_item(product_record)
                if getattr(session, "location_stock", None) is not None:
                    session.location_stock.add_stock(product_id, qty)

        narrative_parts = [check_text, craft_result.narrative]
        if craft_result.xp_gained > 0:
            self.progression.add_xp(session.player, craft_result.xp_gained)

        return ActionResult(
            narrative="\n".join(narrative_parts),
            scene_type=session.dm_context.scene_type,
            state_changes={
                "xp_gained": craft_result.xp_gained,
                "crafted": craft_result.products,
                "_world_minutes": turns_required * 15,
            },
        )

    def _handle_unequip(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Unequip handler (delegates to _handle_unequip_item)."""
        target = (action.target or "").lower()
        return self._handle_unequip_item(session, target)

    def _handle_save_game(self, session: GameSession, action: ParsedAction) -> ActionResult:
        slot_name = (action.target or "").strip() or (
            session.last_save_slot
            if getattr(session, "last_save_slot", None) and not str(session.last_save_slot).startswith("autosave_")
            else "quicksave"
        )
        try:
            self.save_system.save_game(session, slot_name, player_name=session.player.name)
        except Exception as exc:
            return ActionResult(
                narrative=f"Save failed for slot '{slot_name}': {exc}",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        return ActionResult(
            narrative=f"Game saved to '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"save_slot": slot_name, "_skip_world_tick": True},
        )

    def _handle_load_game(self, session: GameSession, action: ParsedAction) -> ActionResult:
        slot_name = (action.target or "").strip() or (
            session.last_save_slot
            if getattr(session, "last_save_slot", None) and not str(session.last_save_slot).startswith("autosave_")
            else "quicksave"
        )
        try:
            loaded = self.save_system.load_game(slot_name, strict=True)
        except FileNotFoundError:
            return ActionResult(
                narrative=f"No save slot named '{slot_name}' exists.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        except Exception as exc:
            return ActionResult(
                narrative=f"Could not load '{slot_name}': {exc}",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )

        session.replace_with(loaded, preserve_session_id=True)
        session.last_save_slot = slot_name
        return ActionResult(
            narrative=f"Loaded save slot '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"save_slot": slot_name, "_skip_world_tick": True},
        )

    def _handle_list_saves(self, session: GameSession, action: ParsedAction) -> ActionResult:
        saves = self.save_system.list_saves()
        if not saves:
            text = "No save slots found."
        else:
            lines = ["Save slots:"]
            for save in saves[:12]:
                lines.append(
                    f"- {save['slot_name']} | {save.get('player_name', 'Unknown')} Lv{save.get('player_level', 1)} | "
                    f"{save.get('location', 'Unknown')} | {save.get('game_time', '')}"
                )
            text = "\n".join(lines)
        return ActionResult(
            narrative=text,
            scene_type=session.dm_context.scene_type,
            state_changes={"_skip_world_tick": True},
        )

    def _handle_delete_save(self, session: GameSession, action: ParsedAction) -> ActionResult:
        slot_name = (action.target or "").strip()
        if not slot_name:
            return ActionResult(
                narrative="Delete which save slot? Try 'delete save quicksave'.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        if not self.save_system.delete_save(slot_name):
            return ActionResult(
                narrative=f"No save slot named '{slot_name}' exists.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        return ActionResult(
            narrative=f"Deleted save slot '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"deleted_slot": slot_name, "_skip_world_tick": True},
        )

    def _build_weapon_item(self, item_data: Optional[Dict[str, Any]]) -> Optional[Item]:
        if not item_data:
            return None
        damage = max(1, int(item_data.get("damage", 4)))
        damage_dice = item_data.get("damage_dice") or f"1d{damage}"
        return Item(
            id=item_data.get("id"),
            name=item_data.get("name", "Weapon"),
            value=int(item_data.get("value", 0)),
            weight=float(item_data.get("weight", 0.0)),
            item_type=ItemType.WEAPON,
            damage_dice=damage_dice,
            damage_type=item_data.get("damage_type", "slashing"),
            armor_bonus=int(item_data.get("ac_bonus", 0)),
        )

    def _character_from_world_entity(self, entity_id: str, entity: Dict[str, Any]) -> Optional[Character]:
        role = entity.get("role") or entity.get("job")
        if not role and entity.get("type") != "npc":
            return None

        stat_presets = {
            "guard": {"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 11},
            "merchant": {"MIG": 8, "AGI": 10, "END": 10, "MND": 10, "INS": 12, "PRE": 13},
            "blacksmith": {"MIG": 14, "AGI": 10, "END": 12, "MND": 9, "INS": 11, "PRE": 10},
            "innkeeper": {"MIG": 10, "AGI": 9, "END": 11, "MND": 10, "INS": 12, "PRE": 12},
            "quest_giver": {"MIG": 9, "AGI": 9, "END": 10, "MND": 12, "INS": 12, "PRE": 13},
            "spy": {"MIG": 9, "AGI": 13, "END": 9, "MND": 11, "INS": 13, "PRE": 11},
        }
        hp = int(entity.get("hp", 10))
        character = Character(
            name=entity.get("name", entity_id),
            hp=hp,
            max_hp=int(entity.get("max_hp", hp)),
            stats=stat_presets.get(role, {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10}),
        )
        character.role = role or "npc"
        character._entity_id = entity_id
        character.equipped_armor = ["shield"] if role == "guard" else []
        character.weapon_material = "iron" if role in {"guard", "blacksmith"} else "wood"
        return character

    def _count_inventory_item(self, session: GameSession, item_id: str) -> int:
        total = 0
        for item in session.inventory:
            if item.get("id") == item_id:
                total += int(item.get("qty", 1))
        return total

    def _accept_quest_offer(self, session: GameSession, offer: Dict[str, Any]) -> Optional[str]:
        quest_id = offer.get("id")
        if not quest_id or session.quest_tracker.get_quest(quest_id):
            return None
        current_hour = self._current_game_hour(session)
        deadline_hours = offer.get("deadline_hours")
        deadline_hour = current_hour + deadline_hours if deadline_hours else None
        session.quest_tracker.add_quest(
            quest_id=quest_id,
            title=offer.get("title", quest_id.replace("_", " ").title()),
            current_hour=current_hour,
            deadline_hour=deadline_hour,
            timeout_consequence=offer.get("timeout_consequence", "quest_failed"),
        )
        session.campaign_state.setdefault("quest_meta", {})[quest_id] = copy.deepcopy(offer)
        session.campaign_state.setdefault("accepted_quests", []).append(quest_id)
        return quest_id

    def _update_quest_progress_for_inventory(self, session: GameSession) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        quest_meta = session.campaign_state.get("quest_meta", {})
        current_hour = self._current_game_hour(session)
        for quest in session.quest_tracker.get_active_quests():
            meta = quest_meta.get(quest.quest_id, {})
            if meta.get("kind") != "delivery":
                continue
            target_item = meta.get("target_item")
            required_qty = int(meta.get("required_qty", 1))
            if target_item and self._count_inventory_item(session, target_item) >= required_qty:
                for _ in range(required_qty):
                    session.remove_item(target_item)
                session.quest_tracker.complete_quest(quest.quest_id, current_hour)
                reward_gold = int(meta.get("reward_gold", 25))
                reward_xp = int(meta.get("reward_xp", 40))
                session.player.gold += reward_gold
                self.progression.add_xp(session.player, reward_xp)
                events.append({
                    "type": "quest_complete",
                    "quest_id": quest.quest_id,
                    "title": quest.title,
                    "reward_gold": reward_gold,
                    "reward_xp": reward_xp,
                })
        return events

    def _update_quest_progress_for_kill(self, session: GameSession, enemy_name: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        quest_meta = session.campaign_state.get("quest_meta", {})
        progress = session.campaign_state.setdefault("quest_progress", {})
        current_hour = self._current_game_hour(session)
        for quest in session.quest_tracker.get_active_quests():
            meta = quest_meta.get(quest.quest_id, {})
            if meta.get("kind") != "hunt":
                continue
            target_name = str(meta.get("target_name", "")).lower()
            if target_name and target_name not in enemy_name.lower():
                continue
            progress[quest.quest_id] = int(progress.get(quest.quest_id, 0)) + 1
            required_kills = int(meta.get("required_kills", 1))
            if progress[quest.quest_id] >= required_kills:
                session.quest_tracker.complete_quest(quest.quest_id, current_hour)
                reward_gold = int(meta.get("reward_gold", 40))
                reward_xp = int(meta.get("reward_xp", 60))
                session.player.gold += reward_gold
                self.progression.add_xp(session.player, reward_xp)
                events.append({
                    "type": "quest_complete",
                    "quest_id": quest.quest_id,
                    "title": quest.title,
                    "reward_gold": reward_gold,
                    "reward_xp": reward_xp,
                })
        return events

    def _generate_emergent_quests(self, session: GameSession, force: bool = False) -> List[Dict[str, Any]]:
        offers: List[Dict[str, Any]] = []
        existing_quests = set(session.quest_tracker.quests.keys())
        shortage_specs = [
            ("bread", "Bread Shortage", "The taverns need fresh bread before tonight.", 2, 20, 35),
            ("ale", "Dry Casks", "Cellars are running low on ale. Bring stock before evening trade.", 2, 18, 35),
            ("healing_potion", "Remedy Run", "The local healer is running short on remedies.", 1, 24, 50),
        ]
        for item_id, title, description, qty, deadline, reward in shortage_specs:
            baseline = session.location_stock.baseline.get(item_id, 0)
            stock = session.location_stock.get_stock(item_id)
            quest_id = f"resupply_{item_id}"
            if quest_id in existing_quests:
                continue
            if force or (baseline and stock <= max(1, baseline // 3)):
                offers.append({
                    "id": quest_id,
                    "kind": "delivery",
                    "title": title,
                    "description": description,
                    "target_item": item_id,
                    "required_qty": qty,
                    "deadline_hours": deadline,
                    "reward_gold": reward,
                    "reward_xp": 40,
                })

        hunt_id = "clear_the_roads"
        if hunt_id not in existing_quests and (force or "road" in session.dm_context.location.lower() or "forest" in session.dm_context.location.lower()):
            offers.append({
                "id": hunt_id,
                "kind": "hunt",
                "title": "Clear The Roads",
                "description": "Predators and raiders have made the roads unsafe. Cut them down.",
                "target_name": "goblin",
                "required_kills": 2,
                "deadline_hours": 36,
                "reward_gold": 60,
                "reward_xp": 75,
            })

        return offers[:3]

    def _step_toward(self, start: tuple, target: tuple) -> tuple:
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
        return (start[0] + step_x, start[1] + step_y)

    def _move_entity_if_possible(self, session: GameSession, entity: Entity, target_pos: tuple) -> bool:
        if tuple(entity.position) == tuple(target_pos):
            return False
        tx, ty = target_pos
        if session.map_data and not session.map_data.is_walkable(tx, ty):
            return False
        if session.spatial_index and session.spatial_index.blocking_at(tx, ty):
            blockers = [candidate for candidate in session.spatial_index.at(tx, ty) if candidate.id != entity.id and candidate.blocking]
            if blockers:
                return False
        if session.spatial_index:
            session.spatial_index.move(entity, tx, ty)
        else:
            entity.move_to(tx, ty)
        return True

    def _merge_world_events(self, session: GameSession, result: ActionResult, world_events: List[Dict[str, Any]]) -> None:
        if not world_events:
            return
        result.state_changes.setdefault("world_events", []).extend(copy.deepcopy(world_events))
        messages: List[str] = []
        for event in world_events:
            event_type = event.get("type")
            if event_type == "quest_complete":
                messages.append(
                    f"Quest complete: {event.get('title', event.get('quest_id', 'Unknown quest'))}. "
                    f"+{event.get('reward_gold', 0)} gold, +{event.get('reward_xp', 0)} XP."
                )
            elif event.get("hours_remaining") is not None:
                messages.append(
                    f"Reminder: {event.get('title', event.get('quest_id', 'A quest'))} has "
                    f"{event.get('hours_remaining')} hours remaining."
                )
            elif event.get("consequence"):
                messages.append(f"Quest failed: {event.get('title', event.get('quest_id', 'Unknown quest'))}.")
            elif event_type == "caravan_arrival":
                messages.append("A caravan arrives and local merchants restock their wares.")
        if messages:
            result.narrative = f"{result.narrative}\n" + "\n".join(messages)

    # --- AP & Skill Check Helpers ---

    def _check_ap(self, session: GameSession, cost_key: str) -> Optional[ActionResult]:
        """Check if player has enough AP. Returns ActionResult on failure, None on success."""
        if session.ap_tracker is None:
            return None  # backward compat
        cost = ACTION_COSTS.get(cost_key, 1)
        if not session.ap_tracker.can_afford(cost):
            return ActionResult(
                narrative=f"Not enough action points! ({session.ap_tracker.current_ap}/{session.ap_tracker.max_ap} AP, need {cost})",
                scene_type=session.dm_context.scene_type,
            )
        session.ap_tracker.spend(cost)
        return None

    def _format_skill_check(self, result: SkillCheckResult, ability_name: str, dc: int) -> str:
        """Format a skill check result for narrative."""
        if result.critical == "success":
            return f"[NATURAL 20! Critical Success on {ability_name} check (DC {dc})]"
        elif result.critical == "failure":
            return f"[NATURAL 1! Critical Failure on {ability_name} check (DC {dc})]"
        elif result.success:
            return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Success by {result.margin}]"
        else:
            return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Failed by {abs(result.margin)}]"

    def _get_player_ability(self, session: GameSession, ability: str) -> int:
        """Get a player's ability score by abbreviation (MIG, AGI, etc.)."""
        return session.player.stats.get(ability, 10)

    # --- Skill-Based Action Handlers ---

    def _handle_search(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Search current area for hidden items/traps/secrets."""
        ap_fail = self._check_ap(session, "search")
        if ap_fail:
            return ap_fail

        dc = 13
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)
        target = action.target or "the area"

        if check_result.success:
            if check_result.critical == "success":
                narrative = f"Your keen eyes discover something remarkable hidden within {target}! A rare find."
            else:
                narrative = f"You carefully search {target} and notice something previously hidden."
        else:
            if check_result.critical == "failure":
                narrative = f"You search {target} carelessly and accidentally trigger something!"
            else:
                narrative = f"You search {target} thoroughly but find nothing of interest."

        desc = f"{session.player.name} searches {target}. {narrative}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name, "action": "search", "target": target,
            "success": check_result.success, "roll": check_result.total,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_steal(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Attempt to steal from an NPC using contested check."""
        ap_fail = self._check_ap(session, "steal")
        if ap_fail:
            return ap_fail

        target = action.target or "someone"
        prox_fail = self._check_entity_proximity(session, target, "steal")
        if prox_fail:
            return prox_fail

        found = self._find_entity_by_name(session, target)
        npc_ins = 12
        if found:
            _, entity = found
            target = entity.get("name", target)

        # Contested check: player AGI vs NPC INS
        player_agi = self._get_player_ability(session, "AGI")
        result_a, result_b, winner = contested_check(player_agi, npc_ins)
        check_text = self._format_skill_check(result_a, "AGI", result_b.total)

        if winner == "a":
            if result_a.critical == "success":
                narrative = f"With incredible sleight of hand, you deftly steal something valuable from {target}!"
            else:
                narrative = f"Your nimble fingers slip into {target}'s belongings unnoticed."
        else:
            if result_a.critical == "failure":
                narrative = f"{target} catches your hand! They shout for the guards!"
            else:
                narrative = f"{target} notices your attempt and pulls away suspiciously."

        desc = f"{session.player.name} attempts to steal from {target}. {'Success' if winner == 'a' else 'Failure'}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "steal", "target": target,
            "success": winner == "a",
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_persuade(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Persuade an NPC with a PRE skill check."""
        ap_fail = self._check_ap(session, "persuade")
        if ap_fail:
            return ap_fail

        target = action.target or "someone"
        prox_fail = self._check_entity_proximity(session, target, "talk")
        if prox_fail:
            return prox_fail

        found = self._find_entity_by_name(session, target)
        if found:
            _, entity = found
            target = entity.get("name", target)

        dc = 13
        ability = "PRE"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"Your words ring true and {target} seems persuaded."
        else:
            narrative = f"{target} remains unconvinced by your plea."

        desc = f"{session.player.name} tries to persuade {target}. {'Succeeds' if check_result.success else 'Fails'}."
        event = DMEvent(type=EventType.DIALOGUE, description=desc, data={
            "player_name": session.player.name, "action": "persuade", "target": target,
            "success": check_result.success,
        })
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_intimidate(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Intimidate an NPC using higher of MIG or PRE."""
        ap_fail = self._check_ap(session, "intimidate")
        if ap_fail:
            return ap_fail

        target = action.target or "someone"
        prox_fail = self._check_entity_proximity(session, target, "talk")
        if prox_fail:
            return prox_fail

        found = self._find_entity_by_name(session, target)
        if found:
            _, entity = found
            target = entity.get("name", target)

        mig = self._get_player_ability(session, "MIG")
        pre = self._get_player_ability(session, "PRE")
        ability, ability_score = ("MIG", mig) if mig >= pre else ("PRE", pre)

        dc = 14
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"{target} cowers before your menacing presence."
        else:
            narrative = f"{target} stands firm, unimpressed by your threats."

        desc = f"{session.player.name} tries to intimidate {target}."
        event = DMEvent(type=EventType.DIALOGUE, description=desc, data={
            "player_name": session.player.name, "action": "intimidate", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_sneak(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Enter stealth mode with AGI check."""
        ap_fail = self._check_ap(session, "sneak")
        if ap_fail:
            return ap_fail

        dc = 13
        ability = "AGI"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = "You melt into the shadows, moving silently. You are now sneaking."
        else:
            if check_result.critical == "failure":
                narrative = "You stumble loudly! Everyone nearby notices you."
            else:
                narrative = "You try to move quietly, but you're spotted."

        desc = f"{session.player.name} attempts to sneak. {'Success' if check_result.success else 'Failure'}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "sneak", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_climb(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Climb a surface using higher of AGI or MIG."""
        ap_fail = self._check_ap(session, "climb")
        if ap_fail:
            return ap_fail

        target = action.target or "the surface"
        dc = 13
        agi = self._get_player_ability(session, "AGI")
        mig = self._get_player_ability(session, "MIG")
        ability, ability_score = ("AGI", agi) if agi >= mig else ("MIG", mig)

        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"You skillfully climb {target}, finding handholds with ease."
        else:
            if check_result.critical == "failure":
                narrative = f"You slip and fall from {target}! A bruising tumble."
            else:
                narrative = f"You struggle to grip {target} and slide back down."

        desc = f"{session.player.name} attempts to climb {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "climb", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_lockpick(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Pick a lock with AGI check. Requires lockpick in inventory."""
        ap_fail = self._check_ap(session, "lock_pick")
        if ap_fail:
            return ap_fail

        target = action.target or "the lock"

        has_lockpick = any(
            "lockpick" in item.get("id", "").lower() or "lockpick" in item.get("name", "").lower()
            for item in session.inventory
        )
        if not has_lockpick:
            return ActionResult(
                narrative="You need a lockpick to attempt this!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 14
        ability = "AGI"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"*Click!* The lock on {target} opens with a satisfying snap."
        else:
            if check_result.critical == "failure":
                # Lockpick breaks on critical failure
                for i, item in enumerate(session.inventory):
                    if "lockpick" in item.get("id", "").lower() or "lockpick" in item.get("name", "").lower():
                        qty = item.get("qty", 1)
                        if qty <= 1:
                            session.inventory.pop(i)
                        else:
                            item["qty"] = qty - 1
                        break
                narrative = f"Your lockpick snaps inside {target}! The lockpick is lost."
            else:
                narrative = f"The lock on {target} resists your attempts."

        desc = f"{session.player.name} attempts to pick the lock on {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "lockpick", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_pray(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Pray at a shrine or temple. INS check for small heal on success."""
        ap_fail = self._check_ap(session, "pray")
        if ap_fail:
            return ap_fail

        target = action.target or "the gods"
        dc = 10
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        state_changes = {}
        if check_result.success:
            heal = max(1, session.player.max_hp // 8)
            session.player.hp = min(session.player.hp + heal, session.player.max_hp)
            state_changes["hp_restored"] = heal
            if check_result.critical == "success":
                narrative = f"A divine light washes over you! You feel blessed. (+{heal} HP)"
            else:
                narrative = f"You feel a warm sense of peace from your prayer. (+{heal} HP)"
        else:
            narrative = "You pray fervently, but the gods do not answer today."

        desc = f"{session.player.name} prays to {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "pray", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
            state_changes=state_changes,
        )

    def _handle_read_item(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Read a book, scroll, sign, or other text."""
        ap_fail = self._check_ap(session, "read")
        if ap_fail:
            return ap_fail

        target = action.target or "the text"
        desc = f"{session.player.name} carefully reads {target}, studying its contents."
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name, "action": "read", "target": target,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=dm_narrative, scene_type=session.dm_context.scene_type)

    def _handle_push(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Push a heavy object with MIG check."""
        ap_fail = self._check_ap(session, "push")
        if ap_fail:
            return ap_fail

        target = action.target or "the object"
        dc = 14
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"With a mighty heave, you push {target}! It grinds forward."
        else:
            narrative = f"You strain against {target}, but it won't budge."

        desc = f"{session.player.name} attempts to push {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "push", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_fish(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Fish with INS check. Requires fishing rod."""
        ap_fail = self._check_ap(session, "fish")
        if ap_fail:
            return ap_fail

        has_rod = any(
            "fishing" in item.get("id", "").lower() or "fishing" in item.get("name", "").lower()
            or "rod" in item.get("id", "").lower()
            for item in session.inventory
        )
        if not has_rod:
            return ActionResult(
                narrative="You need a fishing rod to fish!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 12
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            session.inventory.append({"id": "raw_fish", "name": "Raw Fish", "qty": 1})
            if check_result.critical == "success":
                session.inventory.append({"id": "raw_fish", "name": "Raw Fish", "qty": 1})
                narrative = "You feel a strong tug and pull out two beautiful fish!"
            else:
                narrative = "After a patient wait, you catch a fine fish!"
        else:
            narrative = "You wait patiently, but the fish aren't biting today."

        desc = f"{session.player.name} goes fishing."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "fish", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_mine(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Mine ore with MIG check. Requires pickaxe."""
        ap_fail = self._check_ap(session, "mine")
        if ap_fail:
            return ap_fail

        has_pickaxe = any(
            "pickaxe" in item.get("id", "").lower() or "pickaxe" in item.get("name", "").lower()
            or "pick" in item.get("id", "").lower()
            for item in session.inventory
        )
        if not has_pickaxe:
            return ActionResult(
                narrative="You need a pickaxe to mine!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 12
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            session.inventory.append({"id": "iron_ore", "name": "Iron Ore", "qty": 1})
            if check_result.critical == "success":
                session.inventory.append({"id": "iron_ore", "name": "Iron Ore", "qty": 1})
                narrative = "You strike a rich vein and extract two chunks of quality ore!"
            else:
                narrative = "You chip away at the rock and extract some usable ore."
        else:
            narrative = "You swing your pickaxe but only break off worthless rubble."

        desc = f"{session.player.name} mines for ore."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "mine", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_chop(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Chop a tree for wood with MIG check. Requires axe."""
        ap_fail = self._check_ap(session, "chop")
        if ap_fail:
            return ap_fail

        target = action.target or "a tree"

        has_axe = any(
            "axe" in item.get("id", "").lower() or "axe" in item.get("name", "").lower()
            for item in session.inventory
        )
        if not has_axe:
            return ActionResult(
                narrative="You need an axe to chop wood!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 10
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            session.inventory.append({"id": "wood_plank", "name": "Wood Plank", "qty": 1})
            if check_result.critical == "success":
                session.inventory.append({"id": "wood_plank", "name": "Wood Plank", "qty": 1})
                narrative = f"You fell {target} with powerful strokes, yielding plenty of timber!"
            else:
                narrative = f"You chop {target} into usable planks."
        else:
            narrative = f"You hack at {target} but can't fell it properly. No usable wood."

        desc = f"{session.player.name} chops {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "chop", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    # --- Living World Helpers ---

    def _world_tick(self, session: GameSession, minutes: int = 15, refresh_ap: bool = False) -> list:
        """Advance game time and run all Living World subsystems."""
        events: List[Dict[str, Any]] = []
        if not getattr(session, "game_time", None):
            return events

        before_hour = self._current_game_hour(session)
        previous_period = session.game_time.period
        session.game_time.advance(minutes)
        after_hour = self._current_game_hour(session)
        hours_passed = max(minutes / 60.0, after_hour - before_hour)
        current_period = session.game_time.period
        crossed_hour = int(before_hour) != int(after_hour)

        if session.ap_tracker and (refresh_ap or crossed_hour):
            session.ap_tracker.refresh()

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
                            session.entities[npc.id]["position"] = [npc.position[0], npc.position[1]]
                            session.entities[npc.id]["scheduled_location"] = session.entities[npc.id].get("scheduled_location")
                            session.entities[npc.id]["entity_ref"] = npc
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

        if crossed_hour or refresh_ap:
            for entity in session.entities.values():
                role = entity.get("role")
                for recipe_key in ROLE_PRODUCTION.get(role, ()):
                    try:
                        session.location_stock.produce(recipe_key)
                    except Exception:
                        continue

            caravan_events = session.caravan_manager.tick(int(after_hour))
            for ce in caravan_events:
                if ce.get("type") == "arrival" and ce.get("goods_delivered"):
                    for item, qty in ce["goods_delivered"].items():
                        session.location_stock.add_stock(item, qty)
                    ce = dict(ce)
                    ce["type"] = "caravan_arrival"
                events.append(ce)

            session.rumor_network.decay(hours=max(1.0, hours_passed))
            session.rumor_network.prune_expired()

        quest_result = session.quest_tracker.tick(after_hour)
        if quest_result.get("expired"):
            events.extend(quest_result["expired"])
        if quest_result.get("reminders"):
            events.extend(quest_result["reminders"])

        quest_progress_events = self._update_quest_progress_for_inventory(session)
        if quest_progress_events:
            events.extend(quest_progress_events)

        session.quest_offers = self._generate_emergent_quests(session)
        session.campaign_state["last_world_tick_hour"] = after_hour
        session.narration_context["world_period_changed"] = previous_period != current_period
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

    def _find_entity_by_name(self, session: GameSession, target_name: str) -> Optional[tuple]:
        """Find entity by partial name match. Returns (entity_id, entity_dict) or None."""
        if not target_name:
            return None
        target_lower = target_name.lower()
        for eid, entity in session.entities.items():
            if target_lower in entity.get("name", "").lower() or target_lower in entity.get("role", "").lower():
                return (eid, entity)
        return None

    def _check_entity_proximity(self, session: GameSession, target_name: str, action_type: str) -> Optional[ActionResult]:
        """Check if target entity is in range for action. Returns ActionResult on failure, None if OK."""
        found = self._find_entity_by_name(session, target_name)
        if found is None:
            return None  # No entity found, let the handler deal with it normally
        eid, entity = found
        target_pos = entity.get("position", [0, 0])
        ok, msg = check_proximity(session.position, target_pos, action_type)
        if not ok:
            return ActionResult(
                narrative=f"{msg} {entity['name']} is at position {target_pos}.",
                scene_type=session.dm_context.scene_type,
            )
        return None

    # --- Helpers ---

    def _spawn_enemy(self, player_level: int) -> Character:
        """Spawn a level-appropriate enemy."""
        enemies = [
            Character(name="Goblin",   hp=8,  max_hp=8,
                      stats={"MIG": 8,  "AGI": 14, "END": 8,  "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Orc",      hp=15, max_hp=15,
                      stats={"MIG": 14, "AGI": 8,  "END": 12, "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Skeleton", hp=10, max_hp=10,
                      stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 4, "INS": 6, "PRE": 4}),
        ]
        return random.choice(enemies)

    def _start_combat(self, session: GameSession, enemies: List[Character]) -> None:
        """Initialize a combat encounter."""
        combatants = [session.player] + enemies
        session.combat = CombatManager(combatants, seed=random.randint(0, 9999))
        session.combat.start_turn()
        self.dm.transition(session.dm_context, SceneType.COMBAT)

    def _find_target(
        self,
        combat: CombatManager,
        target_name: Optional[str],
        exclude: str,
    ) -> Optional[int]:
        """Find target combatant index by name, or first living non-player."""
        if target_name:
            for i, c in enumerate(combat.combatants):
                if (target_name.lower() in c.name.lower()
                        and not c.is_dead
                        and c.name != exclude):
                    return i

        for i, c in enumerate(combat.combatants):
            if c.name != exclude and not c.is_dead:
                return i

        return None

    def _combat_state(self, combat: Optional[CombatManager]) -> Optional[dict]:
        """Serialize combat state for API response."""
        if combat is None:
            return None
        return {
            "round": combat.round,
            "active": combat.active_combatant.name if not combat.combat_ended else None,
            "ended": combat.combat_ended,
            "combatants": [
                {
                    "name": c.name,
                    "hp": c.character.hp,
                    "max_hp": c.character.max_hp,
                    "ap": c.ap,
                    "dead": c.is_dead,
                }
                for c in combat.combatants
            ],
        }
