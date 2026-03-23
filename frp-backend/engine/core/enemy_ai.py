"""
Ember RPG - Enemy AI
Tactical AI decision-making for enemy combatants.
"""
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
import random

if TYPE_CHECKING:
    from engine.core.combat import Combatant, CombatManager


@dataclass
class CombatAction:
    """Represents an action chosen by the AI."""
    action_type: str  # "attack", "flee", "special", "heal"
    target_index: Optional[int] = None  # index in combatants list
    special_move: Optional[str] = None  # name of special move if any


class EnemyAI:
    """
    Tactical AI for enemy combatants.

    Decision rules (priority order):
    1. Flee if low HP (beasts only; bosses/undead never flee)
    2. Target healer (priest class) first
    3. Use special moves (30% chance when available)
    4. Focus wounded target (HP < 50%)
    5. Default: attack random valid target
    """

    # Enemy types that never flee
    NEVER_FLEE_TYPES = {"boss", "undead", "construct", "demon"}
    # Enemy types that flee when low HP
    FLEE_TYPES = {"beast", "animal", "humanoid", "goblin", "bandit"}
    LOW_HP_THRESHOLD = 0.20  # 20% of max HP

    def choose_action(self, enemy: 'Combatant', combat_manager: 'CombatManager') -> CombatAction:
        """
        Choose the best action for the enemy this turn.

        Args:
            enemy: The enemy combatant taking the turn
            combat_manager: Full combat state

        Returns:
            CombatAction with action type and optional target
        """
        combatants = combat_manager.combatants
        player_combatants = self._get_player_combatants(enemy, combatants)

        if not player_combatants:
            return CombatAction(action_type="wait")

        # Rule 1: Flee if low HP (only certain enemy types)
        if self._should_flee(enemy):
            return CombatAction(action_type="flee")

        # Rule 2: Target healer/priest first
        healer = self._find_healer(player_combatants, combatants)
        if healer is not None:
            # Rule 3: Use special move against healer?
            if self._should_use_special(enemy):
                special = self._pick_special_move(enemy)
                return CombatAction(action_type="special", target_index=healer, special_move=special)
            return CombatAction(action_type="attack", target_index=healer)

        # Rule 3: Use special move
        if self._should_use_special(enemy):
            target = self._pick_target(player_combatants, combatants)
            special = self._pick_special_move(enemy)
            return CombatAction(action_type="special", target_index=target, special_move=special)

        # Rule 4: Focus wounded target
        wounded = self._find_wounded_target(player_combatants, combatants)
        if wounded is not None:
            return CombatAction(action_type="attack", target_index=wounded)

        # Rule 5: Default — attack random valid target
        target = random.choice(player_combatants)
        return CombatAction(action_type="attack", target_index=target)

    def _get_player_combatants(self, enemy: 'Combatant', combatants: list) -> List[int]:
        """Get indices of alive non-enemy combatants."""
        enemy_idx = combatants.index(enemy)
        # Heuristic: treat first half as players if mixed, or use team attribute
        # We identify enemies as those with enemy_type set, players as those without
        result = []
        for i, c in enumerate(combatants):
            if c.is_dead:
                continue
            if i == enemy_idx:
                continue
            char = c.character
            # If character has no enemy_type, it's a player
            if not getattr(char, 'enemy_type', None):
                result.append(i)
        return result

    def _should_flee(self, enemy: 'Combatant') -> bool:
        """Return True if enemy should flee based on HP and type."""
        char = enemy.character
        enemy_type = getattr(char, 'enemy_type', 'beast')

        # Bosses and undead never flee
        if enemy_type in self.NEVER_FLEE_TYPES:
            return False

        # Check HP threshold
        max_hp = getattr(char, 'max_hp', char.hp)
        if max_hp <= 0:
            return False
        hp_ratio = char.hp / max_hp
        return hp_ratio < self.LOW_HP_THRESHOLD

    def _find_healer(self, player_indices: List[int], combatants: list) -> Optional[int]:
        """Return index of a healer (priest class) in player party, if any."""
        for idx in player_indices:
            char = combatants[idx].character
            classes = getattr(char, 'classes', {})
            if 'priest' in classes:
                return idx
        return None

    def _should_use_special(self, enemy: 'Combatant') -> bool:
        """Return True if enemy should use a special move (30% chance)."""
        char = enemy.character
        special_moves = getattr(char, 'special_moves', [])
        if not special_moves:
            return False
        return random.random() < 0.30

    def _pick_special_move(self, enemy: 'Combatant') -> Optional[str]:
        """Pick a random special move from the enemy's repertoire."""
        special_moves = getattr(enemy.character, 'special_moves', [])
        if special_moves:
            return random.choice(special_moves)
        return None

    def _find_wounded_target(self, player_indices: List[int], combatants: list) -> Optional[int]:
        """Return index of a player with HP < 50% of max, if any."""
        for idx in player_indices:
            char = combatants[idx].character
            max_hp = getattr(char, 'max_hp', char.hp)
            if max_hp > 0 and (char.hp / max_hp) < 0.50:
                return idx
        return None

    def _pick_target(self, player_indices: List[int], combatants: list) -> int:
        """Pick a random valid target."""
        return random.choice(player_indices)
