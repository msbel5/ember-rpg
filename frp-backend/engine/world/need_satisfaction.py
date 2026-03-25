"""
Ember RPG -- NPC Need Satisfaction Engine (Sprint 2, FR-60..FR-62)

Autonomous behaviour layer: when an NPC's needs drop below thresholds
the engine decides what the NPC *does about it* -- eat at a tavern,
chat with a nearby NPC, return to their post, or flee to safety.

Each action is returned as a plain dict so the caller (tick scheduler,
narrative engine, etc.) can render or apply it however it likes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from engine.world.npc_needs import NPCNeeds


@dataclass
class SatisfactionAction:
    """One autonomous action taken by the NPC to satisfy a need."""

    action_type: str          # e.g. "eat", "chat", "return_to_post", "flee"
    need_addressed: str       # which need triggered the action
    description: str          # human-readable narrative snippet
    side_effects: dict = field(default_factory=dict)  # e.g. {"stock_food": -1}

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "need_addressed": self.need_addressed,
            "description": self.description,
            "side_effects": self.side_effects,
        }


class NeedSatisfactionEngine:
    """
    Stateless engine that inspects an NPC's needs plus environment
    and returns a list of autonomous actions the NPC would take.

    Parameters
    ----------
    npc_needs : NPCNeeds
        The NPC's current need values (will be *mutated* when needs
        are satisfied).
    npc_location : str
        Location id where the NPC currently is.
    location_stock : dict
        Mutable dict of stock at the NPC's location.
        Expected keys: ``"food"`` (int), ``"guarded"`` (bool).
    nearby_npcs : list[str]
        Ids of other NPCs close enough to chat with.
    """

    def check_and_satisfy(
        self,
        npc_needs: NPCNeeds,
        npc_location: str,
        location_stock: dict[str, Any],
        nearby_npcs: list[str],
    ) -> list[SatisfactionAction]:
        actions: list[SatisfactionAction] = []

        # --- Sustenance ------------------------------------------------
        actions.extend(
            self._handle_sustenance(npc_needs, npc_location, location_stock)
        )

        # --- Social ----------------------------------------------------
        actions.extend(
            self._handle_social(npc_needs, nearby_npcs)
        )

        # --- Duty ------------------------------------------------------
        actions.extend(
            self._handle_duty(npc_needs, npc_location)
        )

        # --- Safety ----------------------------------------------------
        actions.extend(
            self._handle_safety(npc_needs, npc_location, location_stock)
        )

        return actions

    # ------------------------------------------------------------------
    # Individual need handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_sustenance(
        needs: NPCNeeds,
        location: str,
        stock: dict[str, Any],
    ) -> list[SatisfactionAction]:
        actions: list[SatisfactionAction] = []
        is_tavern = "tavern" in location.lower()
        food_available = stock.get("food", 0) > 0

        # FR-62: sustenance < 15 anywhere -> deviate to tavern
        if needs.sustenance < 15 and not is_tavern:
            actions.append(
                SatisfactionAction(
                    action_type="deviate_to_tavern",
                    need_addressed="sustenance",
                    description="Hunger is overwhelming; heading to the nearest tavern.",
                    side_effects={"destination": "tavern"},
                )
            )
            return actions  # don't eat yet, NPC is on the way

        # FR-60: sustenance < 30 at tavern with food -> eat
        if needs.sustenance < 30 and is_tavern and food_available:
            needs.satisfy("sustenance", 40)
            stock["food"] = stock.get("food", 0) - 1
            actions.append(
                SatisfactionAction(
                    action_type="eat",
                    need_addressed="sustenance",
                    description="Ordered a meal at the tavern.",
                    side_effects={"stock_food": -1, "sustenance_gain": 40},
                )
            )

        return actions

    @staticmethod
    def _handle_social(
        needs: NPCNeeds,
        nearby_npcs: list[str],
    ) -> list[SatisfactionAction]:
        actions: list[SatisfactionAction] = []

        # FR-61: social < 25 with a nearby NPC -> chat
        if needs.social < 25 and nearby_npcs:
            partner = nearby_npcs[0]
            needs.satisfy("social", 15)
            actions.append(
                SatisfactionAction(
                    action_type="chat",
                    need_addressed="social",
                    description=f"Struck up a conversation with {partner}.",
                    side_effects={"chat_partner": partner, "social_gain": 15},
                )
            )

        return actions

    @staticmethod
    def _handle_duty(
        needs: NPCNeeds,
        location: str,
    ) -> list[SatisfactionAction]:
        actions: list[SatisfactionAction] = []

        # duty < 20 -> return to assigned post
        if needs.duty < 20:
            needs.satisfy("duty", 30)
            actions.append(
                SatisfactionAction(
                    action_type="return_to_post",
                    need_addressed="duty",
                    description="Sense of duty kicks in; returning to post.",
                    side_effects={"duty_gain": 30},
                )
            )

        return actions

    @staticmethod
    def _handle_safety(
        needs: NPCNeeds,
        location: str,
        stock: dict[str, Any],
    ) -> list[SatisfactionAction]:
        actions: list[SatisfactionAction] = []
        is_guarded = stock.get("guarded", False)

        # safety < 20 -> flee to guarded zone
        if needs.safety < 20:
            if is_guarded:
                # Already in a guarded zone -- feel safer
                needs.satisfy("safety", 25)
                actions.append(
                    SatisfactionAction(
                        action_type="take_shelter",
                        need_addressed="safety",
                        description="Taking shelter in the guarded zone.",
                        side_effects={"safety_gain": 25},
                    )
                )
            else:
                actions.append(
                    SatisfactionAction(
                        action_type="flee_to_guarded_zone",
                        need_addressed="safety",
                        description="Feeling unsafe; moving to a guarded area.",
                        side_effects={"destination": "guarded_zone"},
                    )
                )

        return actions
