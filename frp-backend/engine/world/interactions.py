"""
Context-sensitive interaction system for Ember RPG.
FR-13, FR-17: Per-tile interaction menus, lock/trap/door chains.

Based on PRD sections 7.3 and 9.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Literal, Optional, Tuple

from engine.world.action_points import ACTION_COSTS
from engine.world.skill_checks import SkillCheckResult, roll_check


# ── Interaction types ────────────────────────────────────────────────

class InteractionType(Enum):
    TALK = auto()
    TRADE = auto()
    ATTACK = auto()
    EXAMINE = auto()
    PICK_UP = auto()
    OPEN = auto()
    LOCK_PICK = auto()
    FORCE_OPEN = auto()
    CRAFT = auto()
    CLIMB = auto()
    SWIM = auto()
    READ = auto()
    PRAY = auto()
    USE = auto()
    PUSH = auto()
    PULL = auto()
    SEARCH = auto()
    STEAL = auto()
    SNEAK = auto()
    INTIMIDATE = auto()
    PERSUADE = auto()
    BRIBE = auto()
    CHOP = auto()
    MINE = auto()
    FISH = auto()
    DISARM_TRAP = auto()
    SET_TRAP = auto()
    BURY = auto()
    REST = auto()
    DRINK = auto()
    FILL = auto()
    CLOSE = auto()
    FOLLOW = auto()
    HIRE = auto()
    FLEE = auto()
    LOOT = auto()
    KICK = auto()


# ── Interaction result ───────────────────────────────────────────────

@dataclass
class InteractionResult:
    """Outcome of performing an interaction."""
    success: bool
    narrative_prompt: str               # Sent to the DM/LLM for narration
    skill_check: Optional[SkillCheckResult] = None
    ap_cost: int = 0
    state_changes: Dict[str, Any] = field(default_factory=dict)


# ── Interaction rule definitions ─────────────────────────────────────
# Maps (target_type, interaction) -> rule dict.
# target_type values: npc_friendly, npc_hostile, door_locked, door_unlocked,
#   chest, chest_locked, chest_trapped, item, workstation, tree, ore_vein,
#   water, bed, corpse, sign, lever, altar, wall, boulder, narrow_gap,
#   bridge, campfire, well, barrel, bookshelf, shrine, trap

InteractionRule = Dict[str, Any]

INTERACTION_RULES: Dict[Tuple[str, InteractionType], InteractionRule] = {
    # ── NPC (friendly) ───────────────────────────────────────────
    ("npc_friendly", InteractionType.TALK): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.TRADE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.PERSUADE): {
        "skill": "PRE", "dc_range": (10, 18), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.INTIMIDATE): {
        "skill": "MIG", "dc_range": (12, 16), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.BRIBE): {
        "skill": "PRE", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": ["gold"],
    },
    ("npc_friendly", InteractionType.STEAL): {
        "skill": "AGI", "dc_range": (14, 20), "ap_cost": 2,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.FOLLOW): {
        "skill": "PRE", "dc_range": (12, 16), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_friendly", InteractionType.HIRE): {
        "skill": "PRE", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": ["gold"],
    },

    # ── NPC (hostile) ────────────────────────────────────────────
    ("npc_hostile", InteractionType.ATTACK): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 2,
        "requirements": [],
    },
    ("npc_hostile", InteractionType.FLEE): {
        "skill": "AGI", "dc_range": (10, 14), "ap_cost": 2,
        "requirements": [],
    },
    ("npc_hostile", InteractionType.SNEAK): {
        "skill": "AGI", "dc_range": (12, 18), "ap_cost": 2,
        "requirements": [],
    },
    ("npc_hostile", InteractionType.INTIMIDATE): {
        "skill": "MIG", "dc_range": (13, 18), "ap_cost": 1,
        "requirements": [],
    },
    ("npc_hostile", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Door (locked) ────────────────────────────────────────────
    ("door_locked", InteractionType.LOCK_PICK): {
        "skill": "AGI", "dc_range": (12, 18), "ap_cost": 2,
        "requirements": ["lockpick"],
    },
    ("door_locked", InteractionType.FORCE_OPEN): {
        "skill": "MIG", "dc_range": (14, 20), "ap_cost": 2,
        "requirements": [],
    },
    ("door_locked", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("door_locked", InteractionType.USE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": ["matching_key"],
    },

    # ── Door (unlocked) ──────────────────────────────────────────
    ("door_unlocked", InteractionType.OPEN): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("door_unlocked", InteractionType.CLOSE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("door_unlocked", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Chest ────────────────────────────────────────────────────
    ("chest", InteractionType.OPEN): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("chest", InteractionType.EXAMINE): {
        "skill": "INS", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": [],
    },
    ("chest", InteractionType.SEARCH): {
        "skill": "INS", "dc_range": (10, 16), "ap_cost": 1,
        "requirements": [],
    },

    ("chest_locked", InteractionType.LOCK_PICK): {
        "skill": "AGI", "dc_range": (12, 18), "ap_cost": 2,
        "requirements": ["lockpick"],
    },
    ("chest_locked", InteractionType.FORCE_OPEN): {
        "skill": "MIG", "dc_range": (14, 18), "ap_cost": 2,
        "requirements": [],
    },
    ("chest_locked", InteractionType.EXAMINE): {
        "skill": "INS", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": [],
    },

    ("chest_trapped", InteractionType.DISARM_TRAP): {
        "skill": "AGI", "dc_range": (14, 20), "ap_cost": 2,
        "requirements": [],
    },
    ("chest_trapped", InteractionType.EXAMINE): {
        "skill": "INS", "dc_range": (12, 18), "ap_cost": 1,
        "requirements": [],
    },

    # ── Item on ground ───────────────────────────────────────────
    ("item", InteractionType.PICK_UP): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("item", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("item", InteractionType.KICK): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Workstation ──────────────────────────────────────────────
    ("workstation", InteractionType.CRAFT): {
        "skill": "MND", "dc_range": (8, 25), "ap_cost": 5,
        "requirements": ["ingredients"],
    },
    ("workstation", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("workstation", InteractionType.USE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Tree ─────────────────────────────────────────────────────
    ("tree", InteractionType.CHOP): {
        "skill": "MIG", "dc_range": (8, 12), "ap_cost": 3,
        "requirements": ["axe"],
    },
    ("tree", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("tree", InteractionType.CLIMB): {
        "skill": "AGI", "dc_range": (10, 16), "ap_cost": 2,
        "requirements": [],
    },

    # ── Ore vein ─────────────────────────────────────────────────
    ("ore_vein", InteractionType.MINE): {
        "skill": "MIG", "dc_range": (10, 16), "ap_cost": 3,
        "requirements": ["pickaxe"],
    },
    ("ore_vein", InteractionType.EXAMINE): {
        "skill": "MND", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": [],
    },

    # ── Water ────────────────────────────────────────────────────
    ("water", InteractionType.DRINK): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("water", InteractionType.FILL): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": ["waterskin"],
    },
    ("water", InteractionType.FISH): {
        "skill": "INS", "dc_range": (10, 14), "ap_cost": 3,
        "requirements": ["fishing_rod"],
    },
    ("water", InteractionType.SWIM): {
        "skill": "END", "dc_range": (10, 16), "ap_cost": 2,
        "requirements": [],
    },

    # ── Bed ──────────────────────────────────────────────────────
    ("bed", InteractionType.REST): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 0,
        "requirements": [],
    },
    ("bed", InteractionType.SEARCH): {
        "skill": "INS", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": [],
    },

    # ── Corpse ───────────────────────────────────────────────────
    ("corpse", InteractionType.LOOT): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("corpse", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("corpse", InteractionType.BURY): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 3,
        "requirements": [],
    },

    # ── Sign / book ──────────────────────────────────────────────
    ("sign", InteractionType.READ): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("sign", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Lever / button ───────────────────────────────────────────
    ("lever", InteractionType.PULL): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("lever", InteractionType.PUSH): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("lever", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Altar ────────────────────────────────────────────────────
    ("altar", InteractionType.PRAY): {
        "skill": "INS", "dc_range": (8, 14), "ap_cost": 1,
        "requirements": [],
    },
    ("altar", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Wall ─────────────────────────────────────────────────────
    ("wall", InteractionType.CLIMB): {
        "skill": "AGI", "dc_range": (12, 18), "ap_cost": 2,
        "requirements": [],
    },
    ("wall", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("wall", InteractionType.SEARCH): {
        "skill": "INS", "dc_range": (14, 18), "ap_cost": 1,
        "requirements": [],
    },

    # ── Boulder ──────────────────────────────────────────────────
    ("boulder", InteractionType.PUSH): {
        "skill": "MIG", "dc_range": (14, 20), "ap_cost": 1,
        "requirements": [],
    },
    ("boulder", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("boulder", InteractionType.CLIMB): {
        "skill": "AGI", "dc_range": (10, 14), "ap_cost": 2,
        "requirements": [],
    },

    # ── Narrow gap ───────────────────────────────────────────────
    ("narrow_gap", InteractionType.SNEAK): {
        "skill": "AGI", "dc_range": (11, 15), "ap_cost": 2,
        "requirements": [],
    },
    ("narrow_gap", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Bridge ───────────────────────────────────────────────────
    ("bridge", InteractionType.CLIMB): {
        "skill": "AGI", "dc_range": (13, 17), "ap_cost": 2,
        "requirements": [],
    },
    ("bridge", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Campfire ─────────────────────────────────────────────────
    ("campfire", InteractionType.REST): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 0,
        "requirements": [],
    },
    ("campfire", InteractionType.USE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("campfire", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Well ─────────────────────────────────────────────────────
    ("well", InteractionType.DRINK): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("well", InteractionType.FILL): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": ["waterskin"],
    },
    ("well", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Barrel ───────────────────────────────────────────────────
    ("barrel", InteractionType.OPEN): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },
    ("barrel", InteractionType.SEARCH): {
        "skill": "INS", "dc_range": (8, 12), "ap_cost": 1,
        "requirements": [],
    },
    ("barrel", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Bookshelf ────────────────────────────────────────────────
    ("bookshelf", InteractionType.READ): {
        "skill": "MND", "dc_range": (8, 18), "ap_cost": 1,
        "requirements": [],
    },
    ("bookshelf", InteractionType.SEARCH): {
        "skill": "INS", "dc_range": (12, 16), "ap_cost": 1,
        "requirements": [],
    },
    ("bookshelf", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Shrine ───────────────────────────────────────────────────
    ("shrine", InteractionType.PRAY): {
        "skill": "INS", "dc_range": (8, 12), "ap_cost": 1,
        "requirements": [],
    },
    ("shrine", InteractionType.EXAMINE): {
        "skill": None, "dc_range": (0, 0), "ap_cost": 1,
        "requirements": [],
    },

    # ── Trap (visible) ───────────────────────────────────────────
    ("trap", InteractionType.DISARM_TRAP): {
        "skill": "AGI", "dc_range": (12, 20), "ap_cost": 2,
        "requirements": [],
    },
    ("trap", InteractionType.SET_TRAP): {
        "skill": "AGI", "dc_range": (12, 16), "ap_cost": 3,
        "requirements": ["trap_kit"],
    },
    ("trap", InteractionType.EXAMINE): {
        "skill": "INS", "dc_range": (10, 14), "ap_cost": 1,
        "requirements": [],
    },
}


# ── Helper: map entity/tile to a target type string ──────────────────

def _classify_target(
    tile: Dict[str, Any],
    entities: List[Dict[str, Any]],
) -> List[str]:
    """Return a list of target-type strings present at the given tile.

    Parameters
    ----------
    tile : dict
        Tile data with keys like ``terrain``, ``flags``, ``items``.
    entities : list of dict
        Entities occupying the tile, each with at least ``entity_type``,
        ``disposition``, and ``alive`` fields.
    """
    targets: List[str] = []

    # Classify entities
    for e in entities:
        etype = e.get("entity_type", "")
        disposition = e.get("disposition", "neutral")
        alive = e.get("alive", True)
        locked = e.get("locked", False)
        trapped = e.get("trapped", False)

        if etype == "npc" and alive:
            if disposition in ("friendly", "neutral"):
                targets.append("npc_friendly")
            else:
                targets.append("npc_hostile")

        elif etype == "door":
            if locked:
                targets.append("door_locked")
            else:
                targets.append("door_unlocked")

        elif etype == "chest":
            if trapped:
                targets.append("chest_trapped")
            elif locked:
                targets.append("chest_locked")
            else:
                targets.append("chest")

        elif etype == "corpse" or (etype == "npc" and not alive):
            targets.append("corpse")

        elif etype == "workstation":
            targets.append("workstation")

        elif etype == "lever":
            targets.append("lever")

        elif etype == "sign" or etype == "book":
            targets.append("sign")

        elif etype == "altar":
            targets.append("altar")

        elif etype == "trap":
            targets.append("trap")

        elif etype == "item":
            targets.append("item")

        elif etype == "bed":
            targets.append("bed")

        elif etype == "barrel":
            targets.append("barrel")

        elif etype == "bookshelf":
            targets.append("bookshelf")

        elif etype == "shrine":
            targets.append("shrine")

        elif etype == "campfire":
            targets.append("campfire")

        elif etype == "well":
            targets.append("well")

    # Classify terrain features
    terrain = tile.get("terrain", "")
    flags = tile.get("flags", set())

    if terrain in ("deep_water", "shallow_water") or "WATER" in flags:
        targets.append("water")

    if terrain == "tree" or "TREE" in flags:
        targets.append("tree")

    if terrain == "ore_vein" or "ORE" in flags:
        targets.append("ore_vein")

    if terrain in ("stone_wall", "wood_wall", "brick_wall", "cave_wall"):
        targets.append("wall")

    if terrain == "boulder" or "BOULDER" in flags:
        targets.append("boulder")

    if terrain == "bridge" or "BRIDGE" in flags:
        targets.append("bridge")

    if terrain == "narrow_gap" or "NARROW" in flags:
        targets.append("narrow_gap")

    # Ground items from tile
    if tile.get("items"):
        if "item" not in targets:
            targets.append("item")

    return targets


# ── Public API ───────────────────────────────────────────────────────

def get_available_interactions(
    tile: Dict[str, Any],
    entities_at_tile: List[Dict[str, Any]],
    player: Dict[str, Any],
) -> List[InteractionType]:
    """Return the list of interactions available at a tile.

    Deduplicates and returns a deterministic ordering.

    Parameters
    ----------
    tile : dict
        Tile data (terrain, flags, items, etc.).
    entities_at_tile : list of dict
        Entities at the tile (NPCs, furniture, etc.).
    player : dict
        Player entity data (used for requirement checks in future).
    """
    targets = _classify_target(tile, entities_at_tile)
    seen: set[InteractionType] = set()
    result: List[InteractionType] = []

    for target_type in targets:
        for (tt, itype), _rule in INTERACTION_RULES.items():
            if tt == target_type and itype not in seen:
                seen.add(itype)
                result.append(itype)

    return result


# ── Interaction handler ──────────────────────────────────────────────

class InteractionHandler:
    """Resolves an interaction into a concrete result with optional skill check."""

    def handle(
        self,
        interaction_type: InteractionType,
        player: Dict[str, Any],
        target: Dict[str, Any],
        context: Dict[str, Any],
    ) -> InteractionResult:
        """Execute an interaction and return the result.

        Parameters
        ----------
        interaction_type : InteractionType
            The action being attempted.
        player : dict
            Player data.  Must include ``abilities`` dict mapping ability
            abbreviations to scores (e.g. ``{"AGI": 14, ...}``).
        target : dict
            Target entity/tile data.  Must include ``target_type`` (str).
        context : dict
            Extra context (e.g. ``dc`` override, ``rng`` for testing).
        """
        target_type = target.get("target_type", "item")
        rule = INTERACTION_RULES.get((target_type, interaction_type))

        if rule is None:
            return InteractionResult(
                success=False,
                narrative_prompt=f"Cannot {interaction_type.name.lower()} this target.",
                ap_cost=0,
            )

        ap_cost = rule["ap_cost"]
        skill = rule["skill"]
        dc_lo, dc_hi = rule["dc_range"]
        state_changes: Dict[str, Any] = {}

        # Determine DC: use context override or midpoint of range
        dc = context.get("dc", (dc_lo + dc_hi) // 2 if dc_hi > 0 else 0)
        rng = context.get("rng", None)

        check_result: Optional[SkillCheckResult] = None

        if skill is not None and dc > 0:
            ability_score = player.get("abilities", {}).get(skill, 10)
            check_result = roll_check(ability_score, dc, _rng=rng)
            success = check_result.success
        else:
            success = True

        # Build narrative prompt for the DM
        action_name = interaction_type.name.lower().replace("_", " ")
        target_name = target.get("name", target_type)

        if success:
            narrative = (
                f"The player successfully performs {action_name} on {target_name}."
            )
            # Common state changes for successful interactions
            if interaction_type == InteractionType.OPEN:
                state_changes["opened"] = True
            elif interaction_type == InteractionType.LOCK_PICK:
                state_changes["locked"] = False
            elif interaction_type == InteractionType.FORCE_OPEN:
                state_changes["locked"] = False
                state_changes["broken"] = True
            elif interaction_type == InteractionType.DISARM_TRAP:
                state_changes["trapped"] = False
            elif interaction_type == InteractionType.PICK_UP:
                state_changes["picked_up"] = True
            elif interaction_type == InteractionType.REST:
                state_changes["rested"] = True
            elif interaction_type == InteractionType.CHOP:
                state_changes["chopped"] = True
            elif interaction_type == InteractionType.MINE:
                state_changes["mined"] = True
            elif interaction_type == InteractionType.CLOSE:
                state_changes["opened"] = False
        else:
            narrative = (
                f"The player fails to {action_name} on {target_name}."
            )
            if check_result and check_result.critical == "failure":
                narrative += " A critical failure — something goes wrong!"

        return InteractionResult(
            success=success,
            narrative_prompt=narrative,
            skill_check=check_result,
            ap_cost=ap_cost,
            state_changes=state_changes,
        )
