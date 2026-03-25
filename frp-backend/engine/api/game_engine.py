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

# Living World imports
from engine.world.proximity import check_proximity, move_cardinal, distance
from engine.world.schedules import GameTime as LivingGameTime, hour_to_period, DEFAULT_SCHEDULES
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

        return session

    def _populate_scene_entities(self, session: GameSession, location: str) -> None:
        """Populate session.entities with NPCs appropriate for the location."""
        session.entities = {}
        loc_lower = location.lower()

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
            # Assign a position near the player
            pos = [session.position[0] + random.randint(-2, 2),
                   session.position[1] + random.randint(-2, 2)]
            needs = NPCNeeds()
            session.entities[npc_id] = {
                "name": name,
                "type": "npc",
                "position": pos,
                "faction": faction,
                "role": role,
                "needs": needs,
                "gender": gender,
            }

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

        # --- Living World: advance time and run world tick ---
        world_events = self._world_tick(session)

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
        # Add FLEE if it exists in ActionIntent
        if hasattr(ActionIntent, "FLEE"):
            handlers[ActionIntent.FLEE] = self._handle_flee

        handler = handlers.get(action.intent, self._handle_unknown)
        return handler(session, action)

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

        if not in_active_combat and action.target and not any(kw in target_lower for kw in hostile_keywords):
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
        result = combat.attack(target_idx)
        state_changes = {}
        narrative_parts = []

        # Identify target for narrative
        target_combatant = None
        if 0 <= target_idx < len(combat.combatants):
            target_combatant = combat.combatants[target_idx]

        hit = result.get("hit", False)
        damage = result.get("damage", 0)
        crit = result.get("crit", False)
        fumble = result.get("fumble", False)

        # --- Body part + material system ---
        hit_part = None
        armor_reduction = 0
        material_bonus = ""
        if hit or crit:
            # Roll hit location
            hit_part = roll_hit_location()
            # Check armor (player has no equipped armor list by default, but support it)
            equipped_armor = getattr(session.player, 'equipped_armor', [])
            armor_reduction = calculate_armor_reduction(hit_part, equipped_armor)
            # Apply weapon material bonus (default iron)
            weapon_material = getattr(session.player, 'weapon_material', 'iron')
            if weapon_material in MATERIALS:
                mat = MATERIALS[weapon_material]
                damage = max(1, int(damage * mat.damage_mult))
                material_bonus = f" ({weapon_material})"
            # Reduce damage by armor
            effective_damage = max(0, damage - armor_reduction)
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
                        dmg = enemy_result.get("damage", 0)
                        # Body part hit location for player damage
                        player_hit_part = roll_hit_location()
                        player_armor = getattr(session.player, 'equipped_armor', [])
                        player_armor_red = calculate_armor_reduction(player_hit_part, player_armor)
                        effective_dmg = max(0, dmg - player_armor_red)
                        # Apply to body part tracker
                        session.body_tracker.apply_damage(player_hit_part, effective_dmg)
                        session.player.hp = max(0, session.player.hp - effective_dmg)
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

        # Rest advances time by 8 hours (extra on top of the 15min from process_action)
        for _ in range(32):  # 32 x 15min = 8 hours
            session.game_time.advance(15)
        # Run caravan/economy ticks for rest period
        game_hour = session.game_time.hour + (session.game_time.day - 1) * 24
        session.caravan_manager.tick(game_hour)
        session.rumor_network.decay(hours=8)
        # NPC needs decay during rest
        for eid, entity in session.entities.items():
            needs = entity.get("needs")
            if isinstance(needs, NPCNeeds):
                needs.tick(hours=8)
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
            state_changes={"hp_restored": heal},
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

        # --- Position tracking (enhanced with proximity module) ---
        DIRECTION_DELTAS = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
        }
        MAP_SIZE = 32
        raw = action.raw_input.lower() if action.raw_input else ""
        dest_lower = dest.lower()

        if dest_lower in ("left", "right"):
            # Turn only, don't move
            turn_map = {
                "left":  {"north": "west", "west": "south", "south": "east", "east": "north"},
                "right": {"north": "east", "east": "south", "south": "west", "west": "north"},
            }
            session.facing = turn_map[dest_lower].get(session.facing, session.facing)
        elif dest_lower in DIRECTION_DELTAS:
            # Cardinal move using proximity module
            session.facing = dest_lower
            new_pos, success, msg = move_cardinal(session.position, dest_lower)
            if success:
                # Clamp to map bounds
                new_pos[0] = max(0, min(MAP_SIZE - 1, new_pos[0]))
                new_pos[1] = max(0, min(MAP_SIZE - 1, new_pos[1]))
                session.position = new_pos
            elif msg:
                return ActionResult(narrative=msg, scene_type=session.dm_context.scene_type)
            session.dm_context.location = dest
        elif dest_lower == "forward":
            # Advance in current facing using proximity module
            new_pos, success, msg = move_cardinal(session.position, session.facing)
            if success:
                new_pos[0] = max(0, min(MAP_SIZE - 1, new_pos[0]))
                new_pos[1] = max(0, min(MAP_SIZE - 1, new_pos[1]))
                session.position = new_pos
            session.dm_context.location = dest
        else:
            # Named destination (tavern etc.) — update location name
            session.dm_context.location = dest

        # --- Coordinate support ("x,y") → set absolute position ---
        import re
        coord_match = re.match(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$", str(dest))
        if coord_match:
            try:
                x = int(coord_match.group(1))
                y = int(coord_match.group(2))
                # Clamp to map bounds
                x = max(0, min(MAP_SIZE - 1, x))
                y = max(0, min(MAP_SIZE - 1, y))
                session.position = [x, y]
            except Exception:
                pass

        world_context = self._build_world_context(session)
        desc = f"{session.player.name} moves toward {dest}.\n{world_context}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name,
            "location": dest,
            "action": f"move to {dest}",
            "world_context": world_context,
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

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

    # --- Living World Helpers ---

    def _world_tick(self, session: GameSession) -> list:
        """Advance game time and run all Living World subsystems."""
        events = []

        # Advance 15 minutes per action
        period_changed = session.game_time.advance(15)

        if period_changed:
            current_period = session.game_time.period

            # NPC schedule movements: update entity positions/locations
            for eid, entity in session.entities.items():
                role = entity.get("role", "merchant")
                schedule = DEFAULT_SCHEDULES.get(role, DEFAULT_SCHEDULES["merchant"])
                new_loc = schedule.get(current_period.value, "home")
                entity["scheduled_location"] = new_loc

            # NPC needs decay (all entities)
            for eid, entity in session.entities.items():
                needs = entity.get("needs")
                if isinstance(needs, NPCNeeds):
                    needs.tick(hours=1)

            # Economy: caravan tick
            game_hour = session.game_time.hour + (session.game_time.day - 1) * 24
            caravan_events = session.caravan_manager.tick(game_hour)
            for ce in caravan_events:
                if ce.get("type") == "arrival" and ce.get("goods_delivered"):
                    # Deliver goods to location stock
                    for item, qty in ce["goods_delivered"].items():
                        session.location_stock.add_stock(item, qty)
            events.extend(caravan_events)

            # Rumor decay
            session.rumor_network.decay(hours=1)
            session.rumor_network.prune_expired()

        # Quest timeout check (every action, not just period changes)
        game_hour = session.game_time.hour + (session.game_time.day - 1) * 24
        quest_result = session.quest_tracker.tick(game_hour)
        if quest_result.get("expired"):
            events.extend(quest_result["expired"])
        if quest_result.get("reminders"):
            events.extend(quest_result["reminders"])

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
