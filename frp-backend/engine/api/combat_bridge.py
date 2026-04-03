"""Combat command bridge: kernel combat authority for attack/defend/flee.

Wires player combat commands to the kernel combat pipeline:
- ``attack <target>`` resolves a full attack via ``resolve_attack``, applies
  damage and wound state to the target, and checks for incapacitation.
- ``defend`` sets a defensive stance flag on the player for one round.
- ``flee`` performs an AGI check (d20 + AGI modifier >= 10) to escape.
"""
from __future__ import annotations

import logging
import re
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.kernel.combat import resolve_attack
from engine.kernel.combat_math import ability_modifier

if TYPE_CHECKING:
    from engine.kernel.actor import ActorRecord, ItemStack
    from engine.api.campaign.context import CampaignContext

logger = logging.getLogger(__name__)

_ATTACK_RE = re.compile(r"^attack\s+(.+)$", re.IGNORECASE)
_DEFEND_RE = re.compile(r"^defend$", re.IGNORECASE)
_FLEE_RE = re.compile(r"^flee$", re.IGNORECASE)


def maybe_handle_combat_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle attack/defend/flee via kernel combat pipeline.

    Returns ``(narrative, "combat", hours)`` or ``None`` if the command
    is not a combat command.
    """
    text = command_text.strip()
    runtime = context.kernel_runtime or {}
    actors: dict[str, Any] = runtime.get("actors", {})
    player: Optional[ActorRecord] = actors.get("player")
    if player is None:
        return None

    match = _ATTACK_RE.match(text)
    if match:
        target_name = match.group(1).strip()
        return _handle_attack(context, actors, player, target_name)

    if _DEFEND_RE.match(text):
        return _handle_defend(player)

    if _FLEE_RE.match(text):
        return _handle_flee(context, player)

    return None


# ---------------------------------------------------------------------------
# Attack
# ---------------------------------------------------------------------------

def _handle_attack(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    """Resolve a full attack against the named target."""
    target = _resolve_combat_target(actors, target_name)
    if target is None:
        return (f"No target '{target_name}' found to attack.", "combat", 0)

    if not getattr(target, "alive", True):
        return (f"{target.identity.display_name} is already dead.", "combat", 0)

    weapon = _get_equipped_weapon(player)
    tick = int(context.session.campaign_state.get("campaign", {}).get("tick", 0))

    result = resolve_attack(player, target, weapon=weapon, seed=tick)

    if not result.hit:
        roll_total = result.attack_roll.total
        defense_total = result.defense.total
        return (
            f"{player.name} attacks {target.name} but misses "
            f"(roll {roll_total} vs AC {defense_total}).",
            "combat",
            0,
        )

    # --- Apply damage ---
    strike = result.strike_resolution
    damage = strike.effective_damage if strike is not None else 0
    target.stats["hp"] = max(0, int(target.stats.get("hp", 0)) - damage)

    # --- Apply wound ---
    wound = strike.wound if strike is not None else None
    if wound is not None:
        wounds_list = target.raw_payload.setdefault("wounds", [])
        wounds_list.append(wound)

    # --- Check incapacitation ---
    killed = False
    if result.incapacitation == "dead" or int(target.stats.get("hp", 0)) <= 0:
        target.alive = False
        killed = True

    # --- Build narrative ---
    parts = [f"{player.name} attacks {target.name} and hits for {damage} damage"]
    if wound is not None:
        parts.append(f"wounding the {wound.body_part_id}")
    if killed:
        parts.append(f"{target.name} is slain")
    narrative = ". ".join(parts) + "."

    logger.info(
        "Combat: %s -> %s, damage=%d, wound=%s, killed=%s",
        player.name, target.name, damage,
        wound.body_part_id if wound else "none", killed,
    )
    return (narrative, "combat", 0)


# ---------------------------------------------------------------------------
# Defend
# ---------------------------------------------------------------------------

def _handle_defend(player: "ActorRecord") -> tuple[str, str, int]:
    """Set a defensive stance on the player for one round."""
    player.raw_payload["defensive_stance"] = True
    return (
        f"{player.name} takes a defensive stance, bracing for incoming attacks.",
        "combat",
        0,
    )


# ---------------------------------------------------------------------------
# Flee
# ---------------------------------------------------------------------------

def _handle_flee(
    context: "CampaignContext",
    player: "ActorRecord",
) -> tuple[str, str, int]:
    """AGI check: d20 + AGI modifier >= 10 to escape combat."""
    tick = int(context.session.campaign_state.get("campaign", {}).get("tick", 0))
    rng = Random(tick)
    d20 = rng.randint(1, 20)
    agi_value = int(player.stats.get("AGI", 10))
    agi_mod = ability_modifier(agi_value)
    total = d20 + agi_mod
    dc = 10

    if total >= dc:
        player.raw_payload["fled_combat"] = True
        return (
            f"{player.name} attempts to flee (d20={d20} + AGI {agi_mod:+d} = {total} vs DC {dc}) "
            f"and escapes successfully!",
            "combat",
            0,
        )
    return (
        f"{player.name} attempts to flee (d20={d20} + AGI {agi_mod:+d} = {total} vs DC {dc}) "
        f"but fails to escape!",
        "combat",
        0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_combat_target(
    actors: dict[str, Any], name: str,
) -> Optional["ActorRecord"]:
    """Find an actor by (partial) name match, excluding the player."""
    lower = name.lower()
    for actor_id, actor in actors.items():
        if actor_id == "player":
            continue
        if hasattr(actor, "identity") and lower in actor.identity.display_name.lower():
            return actor
    return None


def _get_equipped_weapon(player: "ActorRecord") -> Optional["ItemStack"]:
    """Return the player's currently equipped weapon, if any.

    EquipmentLoadout stores ``slots: dict[str, list[ItemStack]]``.
    We look in the "weapon" or "main_hand" slot and return the first item.
    """
    equipment = getattr(player, "equipment", None)
    if equipment is None:
        return None
    slots = getattr(equipment, "slots", {})
    for slot_key in ("weapon", "main_hand"):
        items = slots.get(slot_key)
        if items and isinstance(items, list) and len(items) > 0:
            return items[0]
    return None
