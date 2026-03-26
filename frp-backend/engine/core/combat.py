"""
Ember RPG - Core Engine
Turn-based combat system with D&D-style turn resources layered over the
existing AP-compatible interface.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from engine.core.character import Character
from engine.core.item import Item, ItemType
from engine.core.enemy_ai import EnemyAI, CombatAction
from engine.world.skill_checks import roll_d20
import random


@dataclass
class Condition:
    """Temporary status effect on a combatant."""
    name: str
    duration: int  # turns remaining
    effect: str  # description
    source_id: Optional[str] = None
    
    def apply_turn_effect(self, combatant: 'Combatant') -> Optional[str]:
        """
        Apply per-turn effect (poison damage, burning, etc.).
        
        Args:
            combatant: Target combatant
        
        Returns:
            Log message if effect was applied, None otherwise
        """
        if self.name == "poisoned":
            from engine.core.rules import roll_dice
            damage = roll_dice("1d4")
            combatant.character.hp -= damage
            return f"{combatant.name} takes {damage} poison damage"
        
        if self.name == "burning":
            from engine.core.rules import roll_dice
            damage = roll_dice("1d6")
            combatant.character.hp -= damage
            return f"{combatant.name} takes {damage} fire damage from burning"
        
        return None


@dataclass
class Combatant:
    """Wrapper for characters in combat with combat-specific state."""
    character: Character
    initiative: int
    ap: int = 3  # Action points per turn
    conditions: List[Condition] = field(default_factory=list)
    is_dead: bool = False
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    movement_remaining: int = 6
    speed: int = 6
    disengaged_until_turn_end: bool = False

    @property
    def name(self) -> str:
        return self.character.name

    def has_condition(self, name: str) -> bool:
        lowered = name.lower()
        if lowered in {condition.name.lower() for condition in self.conditions}:
            return True
        return lowered in {condition.lower() for condition in getattr(self.character, "conditions", [])}


class CombatManager:
    """Manages turn-based combat encounters."""
    
    def __init__(self, combatants: List[Character], seed: Optional[int] = None):
        """
        Initialize combat.
        
        Args:
            combatants: List of characters participating in combat
            seed: Random seed for deterministic dice rolls (testing)
        """
        self.rng = random.Random(seed)
        
        self.combatants: List[Combatant] = []
        self.current_turn: int = 0
        self.round: int = 1
        self.log: List[Dict] = []
        self.combat_ended: bool = False
        
        # Roll initiative and sort
        for char in combatants:
            initiative = self.roll_initiative(char)
            self.combatants.append(Combatant(character=char, initiative=initiative))
        
        # Sort by initiative (descending)
        self.combatants.sort(key=lambda c: c.initiative, reverse=True)
        
        self._log_event("combat_start", {
            "combatants": [c.name for c in self.combatants],
            "initiative_order": [(c.name, c.initiative) for c in self.combatants]
        })
    
    def roll_initiative(self, char: Character) -> int:
        """
        Roll initiative (d20 + AGI modifier + initiative_bonus).
        
        Args:
            char: Character rolling initiative
        
        Returns:
            Initiative value
        """
        from engine.core.rules import roll_dice
        roll = self.rng.randint(1, 20)
        agi_mod = char.stat_modifier('AGI')
        return roll + agi_mod + char.initiative_bonus
    
    @property
    def active_combatant(self) -> Combatant:
        """Get the combatant whose turn it is."""
        return self.combatants[self.current_turn]
    
    def start_turn(self):
        """Start a new turn for the active combatant."""
        combatant = self.active_combatant
        combatant.ap = 3  # Reset AP
        combatant.action_available = True
        combatant.bonus_action_available = True
        combatant.reaction_available = True
        combatant.disengaged_until_turn_end = False
        combatant.speed = self._movement_speed(combatant)
        combatant.movement_remaining = combatant.speed
        self._sync_character_condition_names(combatant)

        # Apply condition turn effects (poison, burning, etc.)
        for condition in combatant.conditions[:]:  # Copy to allow removal
            msg = condition.apply_turn_effect(combatant)
            if msg:
                self._log_event("condition_damage", {
                    "combatant": combatant.name,
                    "message": msg
                })
            
            # Decrement duration
            condition.duration -= 1
            if condition.duration <= 0:
                combatant.conditions.remove(condition)
                self._log_event("condition_expired", {
                    "combatant": combatant.name,
                    "condition": condition.name
                })
        self._sync_character_condition_names(combatant)

        # Check death after conditions
        if combatant.character.hp <= 0 and not combatant.is_dead:
            if getattr(combatant.character, "use_death_saves", False):
                death_event = self._resolve_death_save(combatant)
                if death_event:
                    self._log_event("death_save", death_event)
            else:
                combatant.is_dead = True
                self._log_event("death", {"combatant": combatant.name})
                self._check_combat_end()

        if self._cannot_act(combatant):
            combatant.ap = 0
            combatant.action_available = False
            combatant.bonus_action_available = False
            combatant.movement_remaining = 0

        self._log_event("turn_start", {
            "combatant": combatant.name,
            "round": self.round,
            "hp": combatant.character.hp,
            "ap": combatant.ap,
            "resources": self._resources_payload(combatant),
        })

    def attack(self, target_index: int, weapon: Optional[Item] = None) -> Dict:
        """
        Perform an attack action.
        
        Args:
            target_index: Index of target in combatants list
            weapon: Weapon to attack with (uses unarmed if None)
        
        Returns:
            Attack result dictionary with hit/damage/etc.
        """
        attacker = self.active_combatant
        target = self.combatants[target_index]

        # Validation
        if attacker.ap < 1:
            return {"error": "Insufficient AP"}
        if not attacker.action_available or self._cannot_act(attacker):
            return {"error": "No action available"}
        if target.is_dead:
            return {"error": "Target is dead"}

        attacker.ap -= 1
        attacker.action_available = False

        # Default weapon: unarmed strike
        if weapon is None:
            weapon = Item(
                name="Unarmed Strike",
                value=0,
                weight=0,
                item_type=ItemType.WEAPON,
                damage_dice="1d4",
                damage_type="bludgeoning"
            )
        
        # Attack roll: d20 + skill_bonus
        from engine.core.rules import roll_dice
        advantage, disadvantage = self._attack_roll_state(attacker, target)
        roll, rolls = roll_d20(
            advantage=advantage,
            disadvantage=disadvantage,
            _rng=self.rng,
        )
        skill_bonus = attacker.character.skill_bonus("melee")
        attack_roll = roll + skill_bonus
        
        # Hit/crit/fumble logic
        crit = (roll == 20)
        fumble = (roll == 1)
        hit = (attack_roll >= target.character.ac) and not fumble
        
        result = {
            "attacker": attacker.name,
            "target": target.name,
            "roll": roll,
            "skill_bonus": skill_bonus,
            "attack_roll": attack_roll,
            "target_ac": target.character.ac,
            "hit": hit,
            "crit": crit,
            "fumble": fumble,
            "weapon": weapon.name,
            "advantage": advantage and not disadvantage,
            "disadvantage": disadvantage and not advantage,
            "rolls": list(rolls),
        }
        
        if hit:
            # Damage roll
            damage_roll = roll_dice(weapon.damage_dice)
            stat_mod = attacker.character.stat_modifier('MIG')
            
            if crit:
                # Critical: double damage dice, normal modifier
                damage = (damage_roll * 2) + stat_mod
            else:
                damage = damage_roll + stat_mod
            
            # Apply damage
            previous_hp = target.character.hp
            target.character.hp -= damage
            result["damage_roll"] = damage_roll
            result["stat_modifier"] = stat_mod
            result["damage"] = damage
            result["damage_type"] = weapon.damage_type

            # Check death
            if target.character.hp <= 0 and not target.is_dead:
                if getattr(target.character, "use_death_saves", False):
                    target.character.hp = 0
                    self._apply_named_condition(target, "unconscious")
                    result["downed"] = True
                    if previous_hp <= 0:
                        failures = 2 if crit else 1
                        target.character.death_save_failures += failures
                    if target.character.death_save_failures >= 3:
                        target.is_dead = True
                        result["killed"] = True
                        self._log_event("death", {"combatant": target.name})
                else:
                    target.is_dead = True
                    result["killed"] = True
                    self._log_event("death", {"combatant": target.name})

        self._log_event("attack", result)
        self._check_combat_end()
        return result
    
    def use_item(self, item: Item) -> Dict:
        """
        Use a consumable item (potion, scroll, etc.).
        
        Args:
            item: Item to use
        
        Returns:
            Result dictionary with effect messages
        """
        combatant = self.active_combatant

        if combatant.ap < 1:
            return {"error": "Insufficient AP"}
        if not combatant.action_available or self._cannot_act(combatant):
            return {"error": "No action available"}

        combatant.ap -= 1
        combatant.action_available = False
        messages = item.apply_effects(combatant.character)
        
        result = {
            "combatant": combatant.name,
            "item": item.name,
            "effects": messages
        }
        self._log_event("use_item", result)
        return result
    
    def apply_condition(self, target_index: int, condition: Condition) -> Dict:
        """
        Apply a condition to a target.
        
        Args:
            target_index: Index of target combatant
            condition: Condition to apply
        
        Returns:
            Result dictionary
        """
        target = self.combatants[target_index]
        target.conditions.append(condition)
        self._sync_character_condition_names(target)

        result = {
            "target": target.name,
            "condition": condition.name,
            "duration": condition.duration,
            "effect": condition.effect
        }
        self._log_event("condition_applied", result)
        return result
    
    def end_turn(self):
        """End the current turn and advance to next combatant."""
        self.active_combatant.ap = 0  # Spend remaining AP
        self.active_combatant.action_available = False
        self.active_combatant.bonus_action_available = False
        self.active_combatant.disengaged_until_turn_end = False

        # Advance turn
        self.current_turn += 1
        if self.current_turn >= len(self.combatants):
            self.current_turn = 0
            self.round += 1
        
        # Skip dead combatants
        skip_count = 0
        while self.combatants[self.current_turn].is_dead:
            self.current_turn += 1
            if self.current_turn >= len(self.combatants):
                self.current_turn = 0
                self.round += 1
            
            skip_count += 1
            if skip_count >= len(self.combatants):
                # All dead — shouldn't happen if combat_end works
                break
        
        if not self.combat_ended:
            self.start_turn()
    
    def cast_spell(self, spell: 'Spell', target_index: Optional[int] = None) -> Dict:
        """
        Cast a spell during combat.
        
        Args:
            spell: Spell to cast
            target_index: Index of target combatant (for single-target spells)
        
        Returns:
            Spell casting result
        """
        from engine.core.spell import TargetType
        
        caster = self.active_combatant

        # Check AP
        if caster.ap < 2:
            return {"error": "Insufficient AP (casting costs 2 AP)"}
        if not caster.action_available or self._cannot_act(caster):
            return {"error": "No action available"}
        
        # Get target
        target = None
        if spell.target_type == TargetType.SINGLE:
            if target_index is None:
                return {"error": "Single-target spell requires target"}
            target = self.combatants[target_index].character
        
        # Cast spell
        try:
            result = spell.cast(caster.character, target)
            caster.ap -= 2  # Deduct AP after successful cast
            caster.action_available = False
            self._log_event("spell_cast", result)
            return result
        except ValueError as e:
            return {"error": str(e)}

    def disengage(self) -> Dict:
        combatant = self.active_combatant
        if self._cannot_act(combatant) or not combatant.action_available:
            return {"error": "No action available"}
        combatant.action_available = False
        combatant.disengaged_until_turn_end = True
        combatant.ap = max(0, combatant.ap - 1)
        result = {"action": "disengage", "combatant": combatant.name}
        self._log_event("disengage", result)
        return result

    def move_combatant(self, dx: int, dy: int) -> Dict:
        combatant = self.active_combatant
        if combatant.movement_remaining <= 0 or self._cannot_move(combatant):
            return {"error": "No movement remaining"}
        combatant.movement_remaining = max(0, combatant.movement_remaining - max(abs(dx), abs(dy)))
        self._log_event("move", {"combatant": combatant.name, "dx": dx, "dy": dy})
        return {"action": "move", "combatant": combatant.name, "movement_remaining": combatant.movement_remaining}
    
    def _check_combat_end(self):
        """Check if combat has ended (one side eliminated)."""
        alive = [c for c in self.combatants if not c.is_dead]
        if len(alive) <= 1:
            self.combat_ended = True
            winner = alive[0].name if alive else "Nobody"
            self._log_event("combat_end", {
                "winner": winner,
                "rounds": self.round,
                "survivors": len(alive)
            })
    
    def _log_event(self, event_type: str, data: Dict):
        """Log a combat event."""
        self.log.append({
            "type": event_type,
            "round": self.round,
            "data": data
        })

    def _sync_character_condition_names(self, combatant: Combatant) -> None:
        names: List[str] = []
        for condition in combatant.conditions:
            if condition.name not in names:
                names.append(condition.name)
        for existing in list(getattr(combatant.character, "conditions", [])):
            if existing not in names and existing not in {"unconscious"}:
                names.append(existing)
        combatant.character.conditions = names

    def _apply_named_condition(self, combatant: Combatant, name: str, duration: int = 999) -> None:
        if not combatant.has_condition(name):
            combatant.conditions.append(Condition(name=name, duration=duration, effect=name))
        self._sync_character_condition_names(combatant)

    def _remove_named_condition(self, combatant: Combatant, name: str) -> None:
        combatant.conditions = [condition for condition in combatant.conditions if condition.name.lower() != name.lower()]
        combatant.character.conditions = [condition for condition in combatant.character.conditions if condition.lower() != name.lower()]

    def _movement_speed(self, combatant: Combatant) -> int:
        speed = 6
        exhaustion = int(getattr(combatant.character, "exhaustion_level", 0) or 0)
        if exhaustion >= 5 or combatant.has_condition("grappled") or combatant.has_condition("restrained"):
            return 0
        if exhaustion >= 2 or combatant.has_condition("prone"):
            return max(0, speed // 2)
        return speed

    def _cannot_move(self, combatant: Combatant) -> bool:
        return self._movement_speed(combatant) <= 0 or self._cannot_act(combatant)

    def _cannot_act(self, combatant: Combatant) -> bool:
        if combatant.is_dead:
            return True
        if combatant.character.hp <= 0:
            return True
        for blocked in ("incapacitated", "paralyzed", "stunned", "unconscious", "petrified"):
            if combatant.has_condition(blocked):
                return True
        return False

    def _attack_roll_state(self, attacker: Combatant, target: Combatant) -> Tuple[bool, bool]:
        advantage = False
        disadvantage = False
        if attacker.has_condition("blinded") or attacker.has_condition("poisoned") or attacker.has_condition("frightened") or getattr(attacker.character, "exhaustion_level", 0) >= 3:
            disadvantage = True
        if attacker.has_condition("invisible"):
            advantage = True
        if target.has_condition("blinded") or target.has_condition("restrained") or target.has_condition("stunned") or target.has_condition("paralyzed") or target.has_condition("unconscious") or target.has_condition("prone"):
            advantage = True
        if target.has_condition("invisible"):
            disadvantage = True
        return advantage, disadvantage

    def _resolve_death_save(self, combatant: Combatant) -> Dict:
        if combatant.character.death_save_failures >= 3:
            combatant.is_dead = True
            return {"combatant": combatant.name, "result": "dead"}
        if combatant.character.death_save_successes >= 3 or combatant.character.is_stable:
            combatant.character.is_stable = True
            return {"combatant": combatant.name, "result": "stable"}

        roll = self.rng.randint(1, 20)
        payload = {"combatant": combatant.name, "roll": roll}
        if roll == 20:
            combatant.character.hp = 1
            combatant.character.death_save_successes = 0
            combatant.character.death_save_failures = 0
            combatant.character.is_stable = False
            self._remove_named_condition(combatant, "unconscious")
            payload["result"] = "revived"
            return payload
        if roll == 1:
            combatant.character.death_save_failures += 2
        elif roll >= 10:
            combatant.character.death_save_successes += 1
        else:
            combatant.character.death_save_failures += 1

        if combatant.character.death_save_failures >= 3:
            combatant.is_dead = True
            payload["result"] = "dead"
        elif combatant.character.death_save_successes >= 3:
            combatant.character.is_stable = True
            payload["result"] = "stable"
        else:
            payload["result"] = "pending"
        self._apply_named_condition(combatant, "unconscious")
        return payload

    def _resources_payload(self, combatant: Combatant) -> Dict[str, object]:
        return {
            "action_available": combatant.action_available,
            "bonus_action_available": combatant.bonus_action_available,
            "reaction_available": combatant.reaction_available,
            "movement_remaining": combatant.movement_remaining,
            "speed": combatant.speed,
            "disengaged_until_turn_end": combatant.disengaged_until_turn_end,
        }
    
    def enemy_turn(self, ai: Optional['EnemyAI'] = None) -> Dict:
        """
        Process the current combatant's turn using EnemyAI (if it's an enemy).

        Args:
            ai: EnemyAI instance (creates default if None)

        Returns:
            Result dictionary from the chosen action
        """
        if ai is None:
            ai = EnemyAI()

        enemy = self.active_combatant
        action: CombatAction = ai.choose_action(enemy, self)

        if action.action_type == "flee":
            enemy.is_dead = True  # Mark as fled/removed from combat
            self._log_event("flee", {"combatant": enemy.name})
            self._check_combat_end()
            return {"action": "flee", "combatant": enemy.name}

        if action.action_type in ("attack", "special") and action.target_index is not None:
            result = self.attack(action.target_index)
            if action.action_type == "special" and action.special_move:
                result["special_move"] = action.special_move
            return result

        return {"action": "wait", "combatant": enemy.name}

    def get_summary(self) -> Dict:
        """
        Get combat summary.
        
        Returns:
            Dictionary with rounds, survivors, casualties, event count
        """
        return {
            "rounds": self.round,
            "survivors": [c.name for c in self.combatants if not c.is_dead],
            "casualties": [c.name for c in self.combatants if c.is_dead],
            "event_count": len(self.log)
        }
