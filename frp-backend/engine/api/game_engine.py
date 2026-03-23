"""
Ember RPG - API Layer
GameEngine: orchestrates all Phase 2 systems for API actions
"""
from dataclasses import dataclass, field
from typing import Optional, List, Callable
import random

from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.progression import ProgressionSystem
from engine.core.dm_agent import DMAIAgent, DMContext, DMEvent, SceneType, EventType
from engine.api.action_parser import ActionParser, ActionIntent, ParsedAction
from engine.api.game_session import GameSession


# XP rewards for killing enemies (by level)
XP_REWARDS = {1: 100, 2: 200, 3: 450, 4: 700, 5: 1100}


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

        return GameSession(player=player, dm_context=dm_context)

    def process_action(self, session: GameSession, input_text: str) -> ActionResult:
        """
        Process a player's natural language action.

        Args:
            session: Current game session (mutated in-place)
            input_text: Player's raw text input

        Returns:
            ActionResult with narrative and state changes
        """
        session.touch()
        session.dm_context.advance_turn()

        action = self.parser.parse(input_text)

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
            ActionIntent.UNKNOWN:    self._handle_unknown,
        }

        handler = handlers.get(action.intent, self._handle_unknown)
        return handler(session, action)

    # --- Intent Handlers ---

    def _handle_attack(self, session: GameSession, action: ParsedAction) -> ActionResult:
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

        result = combat.attack(target_idx)
        state_changes = {}

        if result.get("crit"):
            desc = f"CRITICAL! {session.player.name} lands a devastating blow — {result.get('damage', 0)} damage!"
        elif result.get("fumble"):
            desc = f"{session.player.name} stumbles — the attack goes wide!"
        elif result.get("hit"):
            desc = f"{session.player.name} strikes — hit! {result.get('damage', 0)} damage."
        else:
            desc = f"{session.player.name} swings but misses."

        combat_state = self._combat_state(combat)
        xp_result = None

        if combat.combat_ended:
            xp = XP_REWARDS.get(session.player.level, 100)
            xp_result = self.progression.add_xp(session.player, xp)
            state_changes["xp_gained"] = xp
            if xp_result:
                state_changes["level_up"] = xp_result.new_level

            event = DMEvent(
                type=EventType.COMBAT_END,
                description=desc,
                data=combat.get_summary(),
            )
            self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        else:
            event = DMEvent(type=EventType.ENCOUNTER, description=desc)

        narrative = self.dm.narrate(event, session.dm_context, self.llm)

        return ActionResult(
            narrative=narrative,
            events=[result],
            state_changes=state_changes,
            scene_type=session.dm_context.scene_type,
            combat_state=combat_state,
            level_up=xp_result,
        )

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
            desc = f"Spell failed: {result['error']}"
        else:
            desc = f"{session.player.name} unleashes {spell.name}!"

        event = DMEvent(type=EventType.ENCOUNTER, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)

        return ActionResult(
            narrative=narrative,
            events=[result],
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(combat),
        )

    def _handle_look(self, session: GameSession, action: ParsedAction) -> ActionResult:
        """Handle 'look around', 'look', 'observe' — scene description at current location."""
        location = session.dm_context.location or "the area"
        desc = (
            f"{session.player.name} surveys their surroundings in {location}. "
            f"Current location: {location}. "
            f"They take in the sights, sounds, and atmosphere of {location} specifically."
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name,
            "location": location,
            "current_location": location,
            "action": "look around",
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_examine(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or session.dm_context.location
        desc = f"{session.player.name} examines {target} closely, looking for details."
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

        # Try to find NPC personality from templates
        npc_personality = self._get_npc_personality(target)

        # Check NPC memory for prior interactions
        npc_id = target.lower().replace(" ", "_")
        memory = session.npc_memory.get_memory(npc_id, npc_name=target)
        prior_context = {}
        if memory and len(memory.conversations) > 0:
            prior_context["prior_interactions"] = len(memory.conversations)
            prior_context["npc_memory_summary"] = memory.build_context()

        desc = (
            f"{session.player.name} approaches {target} to speak. "
            f"{session.player.name} says: (initiate conversation). "
            f"Generate {target}'s response as they would actually speak, "
            f"in character with their personality."
        )
        event_data = {
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "npc_name": target,
            "npc_personality": npc_personality,
            "action": "talk",
            "player_input": action.raw_input,
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
            game_time,
        )

        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

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

        desc = f"{session.player.name} takes a short rest and recovers {heal} HP."
        event = DMEvent(type=EventType.REST, description=desc)
        self.dm.transition(session.dm_context, SceneType.REST)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)

        return ActionResult(
            narrative=narrative,
            state_changes={"hp_restored": heal},
            scene_type=session.dm_context.scene_type,
        )

    def _handle_move(self, session: GameSession, action: ParsedAction) -> ActionResult:
        dest = action.direction or action.target or action.action_detail or "forward"
        # Clean direction strings like "to the tavern" -> "the tavern"
        if dest and dest.startswith("to "):
            dest = dest[3:]
        session.dm_context.location = dest
        desc = f"{session.player.name} moves toward {dest}."
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name,
            "location": dest,
            "action": f"move to {dest}",
        })
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
        npc_personality = self._get_npc_personality(target)
        desc = (
            f"{session.player.name} wants to trade with {target}. "
            f"Generate {target}'s response showing their wares and willingness to trade."
        )
        event = DMEvent(type=EventType.DIALOGUE, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "npc_name": target,
            "npc_personality": npc_personality,
            "action": "trade",
            "player_input": action.raw_input,
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
