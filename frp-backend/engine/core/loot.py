"""
Ember RPG - Loot System
Handles item drops when enemies die in combat.
"""
from typing import List, Optional, TYPE_CHECKING
import random

if TYPE_CHECKING:
    from engine.core.item import Item
    from engine.api.game_session import GameSession

# Rarity → base drop chance (0.0 - 1.0)
RARITY_DROP_CHANCES = {
    "COMMON": 0.50,
    "UNCOMMON": 0.35,
    "RARE": 0.20,
    "EPIC": 0.10,
    "LEGENDARY": 0.05,
}

# Rarity order (lowest first) for guaranteed drop
RARITY_ORDER = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]

# Base drop chance for items without rarity
BASE_DROP_CHANCE = 0.40


class LootSystem:
    """
    Handles loot rolling and inventory application for monster kills.

    Usage:
        loot = LootSystem()
        items = loot.roll_loot(monster_dict, luck_modifier=5)
        acquired = loot.apply_loot_to_session(items, session)
    """

    def roll_loot(self, monster: dict, luck_modifier: int = 0) -> List[str]:
        """
        Roll for loot drops from a monster.

        Args:
            monster: Monster dict with optional 'loot_table', 'type' fields.
                     loot_table items may have 'id', 'rarity' keys.
            luck_modifier: Added to all drop chances (e.g. 5 = +5%)

        Returns:
            List of item IDs that dropped
        """
        loot_table: List[dict] = monster.get("loot_table", [])
        monster_type: str = monster.get("type", "normal")

        if not loot_table:
            return []

        dropped: List[str] = []
        luck_bonus = luck_modifier / 100.0

        for entry in loot_table:
            item_id = entry.get("id") or entry.get("name", "unknown_item")
            rarity = str(entry.get("rarity", "COMMON")).upper()
            base_chance = RARITY_DROP_CHANCES.get(rarity, BASE_DROP_CHANCE)
            chance = min(1.0, base_chance + luck_bonus)
            if random.random() < chance:
                dropped.append(item_id)

        # Guarantee minimum 1 item from any enemy kill
        if not dropped and loot_table:
            dropped.append(self._guaranteed_drop(loot_table))

        # Boss monsters: guarantee 2+ items
        if monster_type == "boss" and len(dropped) < 2:
            candidates = [
                entry.get("id") or entry.get("name", "unknown_item")
                for entry in loot_table
                if (entry.get("id") or entry.get("name")) not in dropped
            ]
            if candidates:
                dropped.append(candidates[0])
            elif loot_table:
                # If all items already dropped, add the first one again (duplicate)
                extra = loot_table[0].get("id") or loot_table[0].get("name", "unknown_item")
                if extra not in dropped:
                    dropped.append(extra)
                elif len(dropped) < 2:
                    dropped.append(extra)  # Allow duplicate for bosses

        return dropped

    def _guaranteed_drop(self, loot_table: List[dict]) -> str:
        """Return the lowest rarity item's ID from the table."""
        best = None
        best_rarity_idx = len(RARITY_ORDER)
        for entry in loot_table:
            rarity = str(entry.get("rarity", "COMMON")).upper()
            idx = RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 0
            if idx < best_rarity_idx:
                best_rarity_idx = idx
                best = entry
        if best:
            return best.get("id") or best.get("name", "unknown_item")
        return loot_table[0].get("id") or loot_table[0].get("name", "unknown_item")

    def apply_loot_to_session(self, item_ids: List[str], session) -> List[str]:
        """
        Add dropped item IDs to the player's inventory in the session.

        Args:
            item_ids: List of item IDs to add
            session: GameSession with player.inventory (list of str IDs or Item objects)

        Returns:
            List of item IDs that were successfully added
        """
        if not item_ids:
            return []

        player = session.player
        if not hasattr(player, 'inventory'):
            player.inventory = []

        acquired = []
        for item_id in item_ids:
            player.inventory.append(item_id)
            acquired.append(item_id)

        return acquired
