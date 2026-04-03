"""Kernel adapter -- clean import boundary for API handlers.

API handlers should import from this module instead of engine.core.
This module exposes kernel combat, actor creation, and effect operations
with ZERO imports from engine.core.

Usage in handlers:
    from engine.api.kernel_adapter import (
        create_player, create_monster, run_attack, start_fight, ...
    )
"""

from __future__ import annotations

from typing import Any

from engine.kernel.actor_records import (
    ActorRecord,
    create_monster_actor,
    create_player_actor,
)
from engine.kernel.combat_engine import (
    AttackResult,
    CombatState,
    CombatantEntry,
    TurnResources,
    TurnStartResult,
    end_turn,
    execute_attack,
    is_combat_over,
    roll_initiative,
    start_combat,
    start_turn,
)
from engine.kernel.combat_resolution import resolve_attack, resolve_strike
from engine.kernel.combat_types import CombatResult, StrikeResolution
from engine.kernel.effects import EffectDef, EffectInstance, EffectQueue
from engine.kernel.actor_body import BodyState, WoundRecord, ConditionRecord
from engine.kernel.actor_items import ItemStack, EquipmentLoadout


# ── Actor creation (replaces Character/Monster constructors) ─────────

def create_player(
    name: str,
    class_name: str,
    stats: dict[str, int],
    **kwargs: Any,
) -> ActorRecord:
    """Create a player ActorRecord from creation data."""
    return create_player_actor(name=name, class_name=class_name, stats=stats, **kwargs)


def create_monster(template: dict[str, Any], **kwargs: Any) -> ActorRecord:
    """Create a monster ActorRecord from a JSON template."""
    return create_monster_actor(template, **kwargs)


# ── Combat operations (replaces CombatManager) ──────────────────────

def start_fight(
    actors: list[ActorRecord],
    seed: int | None = None,
) -> CombatState:
    """Initialize combat encounter with initiative rolls."""
    return start_combat(actors, seed=seed)


def run_attack(
    state: CombatState,
    actors: dict[str, ActorRecord],
    attacker_id: str,
    defender_id: str,
    weapon: ItemStack | None = None,
    seed: int | None = None,
) -> AttackResult:
    """Execute an attack action in combat."""
    return execute_attack(
        state, actors, attacker_id, defender_id,
        weapon=weapon, seed=seed,
    )


def advance_turn(state: CombatState) -> CombatState:
    """End current turn and advance to next combatant."""
    return end_turn(state)


def begin_turn(
    state: CombatState,
    actors: dict[str, ActorRecord],
) -> TurnStartResult:
    """Start the active combatant's turn (reset resources, tick effects)."""
    return start_turn(state, actors)


def check_combat_end(
    state: CombatState,
    actors: dict[str, ActorRecord],
) -> bool:
    """Return True when combat is over (one side eliminated)."""
    return is_combat_over(state, actors)


# ── Actor queries ────────────────────────────────────────────────────

def actor_hp(actor: ActorRecord) -> int:
    """Get actor's current HP."""
    return int(actor.stats.get("hp", 0))


def actor_max_hp(actor: ActorRecord) -> int:
    """Get actor's maximum HP."""
    return int(actor.stats.get("max_hp", 0))


def actor_is_alive(actor: ActorRecord) -> bool:
    """Check if actor is still alive."""
    return actor.alive and actor_hp(actor) > 0


__all__ = [
    "ActorRecord",
    "AttackResult",
    "BodyState",
    "CombatResult",
    "CombatState",
    "CombatantEntry",
    "ConditionRecord",
    "EffectDef",
    "EffectInstance",
    "EffectQueue",
    "EquipmentLoadout",
    "ItemStack",
    "StrikeResolution",
    "TurnResources",
    "TurnStartResult",
    "WoundRecord",
    "actor_hp",
    "actor_is_alive",
    "actor_max_hp",
    "advance_turn",
    "begin_turn",
    "check_combat_end",
    "create_monster",
    "create_player",
    "resolve_attack",
    "resolve_strike",
    "run_attack",
    "start_fight",
]
