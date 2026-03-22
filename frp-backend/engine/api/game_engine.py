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


# Default opening scenes by starting location
_OPENING_SCENES = [
    ("Taş Köprü Meyhanesi", "Alçak tavanlı, tütün kokulu meyhanede oturuyorsunuz. Kor ateş yanıyor ocakta. Kapı gıcırdadı — birisi girdi."),
    ("Orman Yolu", "Sisi kesen sabah güneşinde ilerliyorsunuz. Ağaç dalları üzerinizde kavuşuyor. Uzaktan bir kurt uluması geliyor."),
    ("Liman Kasabası", "Tuzlu deniz havası burnunuzu doluyor. Iskelede balıkçılar ağ topluyor. Bir gemide Kuzey Krallığı bayrağı dalgalanıyor."),
]


class GameEngine:
    """
    Orchestrates all game systems for API-level action processing.

    The engine translates player natural language into game mechanics,
    resolves outcomes, and returns DM narrative.

    Usage:
        engine = GameEngine()
        session = engine.new_session("Aria", "warrior")
        result = engine.process_action(session, "ejderhaya saldırıyorum")
    """

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        """
        Initialize game engine.

        Args:
            llm: Optional LLM backend callable(prompt) -> str
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
            location: Starting location (random if None)

        Returns:
            Initialized GameSession
        """
        # Default stats by class
        class_stats = {
            "warrior": {"MIG": 16, "AGI": 12, "END": 14, "MND": 8, "INS": 10, "PRE": 10},
            "rogue":   {"MIG": 10, "AGI": 16, "END": 10, "MND": 10, "INS": 14, "PRE": 12},
            "mage":    {"MIG": 8,  "AGI": 12, "END": 10, "MND": 16, "INS": 14, "PRE": 10},
            "priest":  {"MIG": 10, "AGI": 10, "END": 12, "MND": 14, "INS": 16, "PRE": 12},
        }
        class_hp = {"warrior": 20, "rogue": 16, "mage": 12, "priest": 16}
        class_sp = {"warrior": 0, "rogue": 0, "mage": 16, "priest": 12}

        stats = class_stats.get(player_class.lower(), class_stats["warrior"])
        hp = class_hp.get(player_class.lower(), 16)
        sp = class_sp.get(player_class.lower(), 0)

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
        return session

    def process_action(
        self,
        session: GameSession,
        input_text: str,
    ) -> ActionResult:
        """
        Process a player's natural language action.

        Args:
            session: Current game session (mutated)
            input_text: Player's raw text input

        Returns:
            ActionResult with narrative and state changes
        """
        session.touch()
        session.dm_context.advance_turn()

        action = self.parser.parse(input_text)

        # Route to handler by intent
        handlers = {
            ActionIntent.ATTACK: self._handle_attack,
            ActionIntent.CAST_SPELL: self._handle_spell,
            ActionIntent.USE_ITEM: self._handle_use_item,
            ActionIntent.EXAMINE: self._handle_examine,
            ActionIntent.TALK: self._handle_talk,
            ActionIntent.REST: self._handle_rest,
            ActionIntent.MOVE: self._handle_move,
            ActionIntent.OPEN: self._handle_open,
            ActionIntent.UNKNOWN: self._handle_unknown,
        }

        handler = handlers.get(action.intent, self._handle_unknown)
        return handler(session, action)

    # --- Intent Handlers ---

    def _handle_attack(self, session: GameSession, action: ParsedAction) -> ActionResult:
        if not session.in_combat():
            # Spawn a random enemy encounter
            enemy = self._spawn_enemy(session.player.level)
            self._start_combat(session, [enemy])

        combat = session.combat
        # Find target by name or pick first living enemy
        target_idx = self._find_target(combat, action.target, exclude=session.player.name)

        if target_idx is None:
            return ActionResult(
                narrative="Saldıracak hedef bulunamadı.",
                scene_type=session.dm_context.scene_type,
            )

        # Ensure player's turn (simplified: player always goes first via initiative_bonus)
        result = combat.attack(target_idx)
        state_changes = {}

        if result.get("hit"):
            desc = (
                f"{session.player.name} saldırıyor — isabet! "
                f"{result.get('damage', 0)} hasar."
            )
        elif result.get("crit"):
            desc = f"KRİTİK! {session.player.name} yıkıcı bir darbe indiriyor!"
        elif result.get("fumble"):
            desc = f"Tutarsız hareket — {session.player.name} tutunuyor!"
        else:
            desc = f"{session.player.name} saldırıyor ama kaçırıyor."

        # Check combat end
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
                narrative="Büyü gücün tükenmiş. Dinlenmen gerekiyor.",
                scene_type=session.dm_context.scene_type,
            )

        # Default: magic missile (placeholder until spell selection is implemented)
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
                narrative="Büyü için hedef bulunamadı.",
                scene_type=session.dm_context.scene_type,
            )

        result = combat.cast_spell(spell, target_idx)

        if "error" in result:
            desc = f"Büyü başarısız: {result['error']}"
        else:
            desc = f"{session.player.name} büyü fırlatıyor — {spell.name}!"

        event = DMEvent(type=EventType.ENCOUNTER, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)

        return ActionResult(
            narrative=narrative,
            events=[result],
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(combat),
        )

    def _handle_examine(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or session.dm_context.location
        desc = f"'{target}' inceliyor musunuz? Dikkatle bakıyorsunuz..."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    def _handle_talk(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or "yabancı biri"
        desc = f"{session.player.name}, {target} ile konuşmak istiyor."
        event = DMEvent(type=EventType.DIALOGUE, description=desc)
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    def _handle_rest(self, session: GameSession, action: ParsedAction) -> ActionResult:
        if session.in_combat():
            return ActionResult(
                narrative="Savaşın ortasında dinlenemezsin!",
                scene_type=session.dm_context.scene_type,
            )

        # Restore HP and spell points
        heal = max(1, session.player.max_hp // 4)
        session.player.hp = min(session.player.hp + heal, session.player.max_hp)
        session.player.spell_points = session.player.max_spell_points

        desc = f"{session.player.name} kısa bir mola veriyor. {heal} HP kazandı."
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
        dest = action.target or "ileri"
        session.dm_context.location = dest
        desc = f"{session.player.name} {dest} doğru ilerliyor."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    def _handle_open(self, session: GameSession, action: ParsedAction) -> ActionResult:
        target = action.target or "kapı"
        desc = f"{session.player.name} {target}ı açmaya çalışıyor."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    def _handle_use_item(self, session: GameSession, action: ParsedAction) -> ActionResult:
        desc = f"{session.player.name} bir eşya kullanmaya çalışıyor."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    def _handle_unknown(self, session: GameSession, action: ParsedAction) -> ActionResult:
        desc = f"'{action.raw_input}' — tam olarak ne yapmak istediğini anlayamadım."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
        )

    # --- Helpers ---

    def _spawn_enemy(self, player_level: int) -> Character:
        """Spawn a level-appropriate enemy."""
        enemies = [
            Character(name="Goblin", hp=8, max_hp=8,
                      stats={"MIG": 8, "AGI": 14, "END": 8, "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Orc", hp=15, max_hp=15,
                      stats={"MIG": 14, "AGI": 8, "END": 12, "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Skeleton", hp=10, max_hp=10,
                      stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 4, "INS": 6, "PRE": 4}),
        ]
        return random.choice(enemies)

    def _start_combat(self, session: GameSession, enemies: List[Character]):
        """Initialize combat with enemies."""
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
        """Find target combatant index by name or first living non-player."""
        if target_name:
            for i, c in enumerate(combat.combatants):
                if (target_name.lower() in c.name.lower()
                        and not c.is_dead
                        and c.name != exclude):
                    return i

        # Fallback: first living non-player combatant
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
