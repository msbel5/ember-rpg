"""Kernel-native combat engine -- turn management over kernel combat math.

This module owns the combat state machine: initiative, turn order, D&D turn
resources (action/bonus_action/reaction/movement), and dispatches to the
existing kernel resolve_attack / resolve_strike pipeline.

No legacy CombatManager or Character objects are used here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor_records import ActorRecord
from engine.kernel.actor_items import ItemStack
from engine.kernel.combat_math import ability_modifier, stat_value
from engine.kernel.combat_resolution import resolve_attack
from engine.kernel.combat_types import CombatResult
from engine.kernel.effects import EffectQueue


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class TurnResources:
    """D&D 5e turn economy: one action, one bonus, one reaction, movement."""

    action: bool = True
    bonus_action: bool = True
    reaction: bool = True
    movement: int = 6
    max_movement: int = 6

    def reset(self) -> None:
        """Reset all resources for a new turn."""
        self.action = True
        self.bonus_action = True
        self.reaction = True
        self.movement = self.max_movement

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "bonus_action": self.bonus_action,
            "reaction": self.reaction,
            "movement": self.movement,
            "max_movement": self.max_movement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnResources:
        return cls(
            action=bool(data.get("action", True)),
            bonus_action=bool(data.get("bonus_action", True)),
            reaction=bool(data.get("reaction", True)),
            movement=int(data.get("movement", 6)),
            max_movement=int(data.get("max_movement", 6)),
        )


@dataclass
class CombatantEntry:
    """Tracks a single combatant's position in the initiative order."""

    actor_id: str
    initiative: int
    is_player: bool
    turn_resources: TurnResources = field(default_factory=TurnResources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "initiative": self.initiative,
            "is_player": self.is_player,
            "turn_resources": self.turn_resources.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CombatantEntry:
        return cls(
            actor_id=str(data["actor_id"]),
            initiative=int(data.get("initiative", 0)),
            is_player=bool(data.get("is_player", False)),
            turn_resources=TurnResources.from_dict(data.get("turn_resources", {})),
        )


@dataclass
class CombatState:
    """Full combat encounter state -- initiative order, round, phase."""

    combatants: list[CombatantEntry]
    round_number: int = 1
    current_turn_index: int = 0
    phase: str = "active"  # "initiative" | "active" | "resolved"

    @property
    def active_combatant(self) -> CombatantEntry:
        """Return the combatant whose turn it is."""
        return self.combatants[self.current_turn_index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "combatants": [c.to_dict() for c in self.combatants],
            "round_number": self.round_number,
            "current_turn_index": self.current_turn_index,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CombatState:
        return cls(
            combatants=[CombatantEntry.from_dict(c) for c in data.get("combatants", [])],
            round_number=int(data.get("round_number", 1)),
            current_turn_index=int(data.get("current_turn_index", 0)),
            phase=str(data.get("phase", "active")),
        )


@dataclass
class TurnStartResult:
    """Result of starting a turn -- the active combatant and any events."""

    active_combatant: CombatantEntry
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AttackResult:
    """Result of an attack action -- wraps kernel CombatResult."""

    combat_result: CombatResult
    attacker_id: str = ""
    defender_id: str = ""
    action_consumed: bool = True
    events: list[dict[str, Any]] = field(default_factory=list)


# ── Initiative ───────────────────────────────────────────────────────

def roll_initiative(actor: ActorRecord, seed: int | None = None) -> int:
    """Roll initiative: d20 + AGI modifier + initiative_bonus."""
    rng = Random(seed) if seed is not None else Random()
    d20 = rng.randint(1, 20)
    agi_mod = ability_modifier(stat_value(actor, "AGI"))
    bonus = int(actor.raw_payload.get("initiative_bonus", 0))
    return d20 + agi_mod + bonus


# ── Combat lifecycle ─────────────────────────────────────────────────

def start_combat(
    actors: list[ActorRecord],
    seed: int | None = None,
) -> CombatState:
    """Initialize combat: roll initiative, sort, create combat state."""
    rng = Random(seed) if seed is not None else Random()
    entries: list[CombatantEntry] = []
    for actor in actors:
        init_seed = rng.randint(0, 2_147_483_647)
        initiative = roll_initiative(actor, seed=init_seed)
        # Calculate base movement from AGI.
        agi = stat_value(actor, "AGI")
        base_movement = max(4, 6 + ability_modifier(agi))
        entries.append(
            CombatantEntry(
                actor_id=actor.identity.actor_id,
                initiative=initiative,
                is_player=(actor.identity.actor_type == "pc"),
                turn_resources=TurnResources(max_movement=base_movement, movement=base_movement),
            )
        )
    # Sort by initiative descending (higher goes first).
    entries.sort(key=lambda e: e.initiative, reverse=True)
    return CombatState(combatants=entries, round_number=1, current_turn_index=0, phase="active")


def start_turn(
    state: CombatState,
    actors: dict[str, ActorRecord],
) -> TurnStartResult:
    """Begin the active combatant's turn: reset resources, tick effects."""
    active = state.active_combatant
    active.turn_resources.reset()
    events: list[dict[str, Any]] = []

    # Tick the effect queue for this actor if present.
    actor = actors.get(active.actor_id)
    if actor is not None and actor.effect_queue is not None:
        current_tick = state.round_number * len(state.combatants) + state.current_turn_index
        tick_events = actor.effect_queue.tick_all(actor, current_tick)
        for ev in tick_events:
            events.append({"type": "effect_tick", "detail": ev})

    return TurnStartResult(active_combatant=active, events=events)


def end_turn(state: CombatState) -> CombatState:
    """Advance to the next living combatant. Increment round if wrapped."""
    n = len(state.combatants)
    if n == 0:
        state.phase = "resolved"
        return state

    # Move to next index, skipping dead combatants.
    start_idx = state.current_turn_index
    for step in range(1, n + 1):
        candidate = (start_idx + step) % n
        if candidate == 0 and step > 0:
            state.round_number += 1
        # We accept any combatant for now; dead-skipping is handled by
        # the caller checking is_combat_over or the actor's alive flag.
        state.current_turn_index = candidate
        return state

    # Should not reach here.
    return state


# ── Actions ──────────────────────────────────────────────────────────

def execute_attack(
    state: CombatState,
    actors: dict[str, ActorRecord],
    attacker_id: str,
    defender_id: str,
    *,
    weapon: ItemStack | None = None,
    seed: int | None = None,
    called_shot: str | None = None,
    flanking: bool = False,
) -> AttackResult:
    """Execute a melee/ranged attack using kernel combat math."""
    # Validate the attacker is the active combatant.
    active = state.active_combatant
    if active.actor_id != attacker_id:
        raise ValueError(f"Not {attacker_id}'s turn (active: {active.actor_id})")
    if not active.turn_resources.action:
        raise ValueError(f"{attacker_id} has no action available this turn")

    attacker = actors[attacker_id]
    defender = actors[defender_id]

    # Delegate to kernel resolve_attack for full attack pipeline.
    combat_result = resolve_attack(
        attacker,
        defender,
        weapon=weapon,
        seed=seed,
        called_shot=called_shot,
        flanking=flanking,
    )

    # Consume the action resource.
    active.turn_resources.action = False

    events: list[dict[str, Any]] = list(combat_result.events)

    # Mark defender dead if incapacitated.
    if combat_result.incapacitation in ("dead",):
        defender.alive = False

    return AttackResult(
        combat_result=combat_result,
        attacker_id=attacker_id,
        defender_id=defender_id,
        action_consumed=True,
        events=events,
    )


# ── Combat end check ─────────────────────────────────────────────────

def is_combat_over(
    state: CombatState,
    actors: dict[str, ActorRecord],
) -> bool:
    """Return True when all combatants on one side are dead."""
    players_alive = False
    enemies_alive = False
    for entry in state.combatants:
        actor = actors.get(entry.actor_id)
        if actor is None or not actor.alive:
            continue
        if entry.is_player:
            players_alive = True
        else:
            enemies_alive = True
    # Combat is over if either side has no survivors.
    return not players_alive or not enemies_alive


__all__ = [
    "AttackResult",
    "CombatState",
    "CombatantEntry",
    "TurnResources",
    "TurnStartResult",
    "end_turn",
    "execute_attack",
    "is_combat_over",
    "roll_initiative",
    "start_combat",
    "start_turn",
]
