"""Quest handler methods for GameEngine — mixin class."""
from __future__ import annotations

import copy
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.api.game_session import GameSession
from engine.api.action_parser import ParsedAction
from engine.world.proximity import check_proximity

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult


class QuestMixin:
    """Quest-related handler methods."""

    def _handle_accept_quest(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        offer = self._match_quest_offer(session, action.target or "")
        if offer is None:
            return ActionResult(
                narrative="No available quest matches that request. Talk to a quest giver first or specify the quest title.",
                scene_type=session.dm_context.scene_type,
            )

        giver = self._resolve_quest_giver(session)
        if offer.get("kind") == "delivery" and giver is None:
            return ActionResult(
                narrative="That delivery quest is not bound to a real giver yet. Talk to the quest giver in person first.",
                scene_type=session.dm_context.scene_type,
            )
        giver_id = giver[0] if giver else None
        giver_name = giver[1].get("name") if giver else None
        accepted = self._accept_quest_offer(session, offer, giver_entity_id=giver_id, giver_name=giver_name)
        if not accepted:
            return ActionResult(
                narrative=f"You are already tracking '{offer.get('title', 'that quest')}'.",
                scene_type=session.dm_context.scene_type,
            )

        session.quest_offers = [candidate for candidate in session.quest_offers if candidate.get("id") != accepted]
        return ActionResult(
            narrative=f"Quest accepted: {offer.get('title', accepted)}.",
            scene_type=session.dm_context.scene_type,
            state_changes={"accepted_quest": accepted},
        )

    def _handle_turn_in_quest(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        resolved = self._turn_in_target_quest(session, action.target or "")
        if resolved is None:
            return ActionResult(
                narrative="No active delivery quest matches that request.",
                scene_type=session.dm_context.scene_type,
            )

        quest, meta = resolved
        giver_id = meta.get("giver_entity_id")
        giver_name = meta.get("giver_name") or "the quest giver"
        if not giver_id:
            return ActionResult(
                narrative=f"'{quest.title}' is missing a bound giver and cannot be turned in until it is reissued properly.",
                scene_type=session.dm_context.scene_type,
            )
        if giver_id and giver_id in session.entities:
            target_pos = session.entities[giver_id].get("position", [0, 0])
            ok, msg = check_proximity(session.position, target_pos, "talk")
            if not ok:
                return ActionResult(
                    narrative=f"{msg} {giver_name} is at position {target_pos}.",
                    scene_type=session.dm_context.scene_type,
                )

        target_item = meta.get("target_item")
        required_qty = int(meta.get("required_qty", 1))
        current_qty = self._count_inventory_item(session, target_item) if target_item else 0
        if not target_item or current_qty < required_qty:
            item_name = str(target_item or "the required item").replace("_", " ")
            return ActionResult(
                narrative=f"You still need {required_qty - current_qty} more {item_name}.",
                scene_type=session.dm_context.scene_type,
            )

        for _ in range(required_qty):
            session.remove_item(target_item)

        current_hour = self._current_game_hour(session)
        session.quest_tracker.complete_quest(quest.quest_id, current_hour)
        reward_gold = int(meta.get("reward_gold", 25))
        reward_xp = int(meta.get("reward_xp", 40))
        session.player.gold += reward_gold
        self.progression.add_xp(session.player, reward_xp)
        completed = session.campaign_state.setdefault("completed_quests", [])
        if quest.quest_id not in completed:
            completed.append(quest.quest_id)
        completed_ids = session.campaign_state.setdefault("completed_quest_ids", [])
        if quest.quest_id not in completed_ids:
            completed_ids.append(quest.quest_id)
        accepted = session.campaign_state.setdefault("accepted_quests", [])
        if quest.quest_id in accepted:
            accepted.remove(quest.quest_id)
        event = {
            "type": "quest_complete",
            "quest_id": quest.quest_id,
            "title": quest.title,
            "reward_gold": reward_gold,
            "reward_xp": reward_xp,
        }
        return ActionResult(
            narrative=(
                f"You turn in '{quest.title}' to {giver_name}. "
                f"+{reward_gold} gold, +{reward_xp} XP."
            ),
            scene_type=session.dm_context.scene_type,
            state_changes={"turned_in_quest": quest.quest_id, "world_events": [event]},
        )

    # --- Quest helpers ---

    def _get_nearby_quest_givers(self, session: GameSession, max_dist: int = 1) -> List[tuple[str, Dict[str, Any]]]:
        givers: List[tuple[str, Dict[str, Any]]] = []
        for entity_id, entity in session.entities.items():
            if entity.get("role") not in {"quest_giver", "guard", "merchant"}:
                continue
            target_pos = entity.get("position", [0, 0])
            if max(abs(session.position[0] - target_pos[0]), abs(session.position[1] - target_pos[1])) <= max_dist:
                givers.append((entity_id, entity))
        return givers

    def _match_quest_offer(self, session: GameSession, query: str) -> Optional[Dict[str, Any]]:
        offers = list(session.quest_offers or [])
        if not offers:
            return None

        query_lower = (query or "").strip().lower()
        generic_queries = {"", "quest", "the quest", "a quest", "görev", "görevi"}
        if query_lower and query_lower not in generic_queries:
            for offer in offers:
                title = str(offer.get("title", "")).lower()
                offer_id = str(offer.get("id", "")).lower()
                if query_lower == title or query_lower == offer_id or query_lower in title:
                    return offer

        last_offer_ids = list(session.narration_context.get("last_shown_quest_offer_ids", []))
        if last_offer_ids:
            prioritized = [offer for offer in offers if offer.get("id") in last_offer_ids]
            if len(prioritized) == 1:
                return prioritized[0]
            if query_lower in generic_queries and prioritized:
                return prioritized[0]

        if len(offers) == 1 or query_lower in generic_queries:
            return offers[0]
        return None

    def _resolve_quest_giver(self, session: GameSession) -> Optional[tuple[str, Dict[str, Any]]]:
        giver_id = session.narration_context.get("last_quest_giver_id")
        if giver_id and giver_id in session.entities:
            return giver_id, session.entities[giver_id]
        nearby = self._get_nearby_quest_givers(session)
        if len(nearby) == 1:
            return nearby[0]
        return None

    def _turn_in_target_quest(self, session: GameSession, query: str) -> Optional[tuple[Any, Dict[str, Any]]]:
        active_quests = session.quest_tracker.get_active_quests()
        quest_meta = session.campaign_state.get("quest_meta", {})
        query_lower = (query or "").strip().lower()
        candidates = []
        for quest in active_quests:
            meta = quest_meta.get(quest.quest_id, {})
            if meta.get("kind") != "delivery":
                continue
            if query_lower and query_lower not in {"quest", "the quest", "a quest", "görev", "görevi"}:
                if query_lower not in quest.title.lower() and query_lower not in quest.quest_id.lower():
                    continue
            candidates.append((quest, meta))

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        giver_id = session.narration_context.get("last_quest_giver_id")
        if giver_id:
            giver_matches = [candidate for candidate in candidates if candidate[1].get("giver_entity_id") == giver_id]
            if len(giver_matches) == 1:
                return giver_matches[0]

        nearby = self._get_nearby_quest_givers(session)
        nearby_ids = {entity_id for entity_id, _ in nearby}
        giver_matches = [candidate for candidate in candidates if candidate[1].get("giver_entity_id") in nearby_ids]
        if len(giver_matches) == 1:
            return giver_matches[0]
        return None

    def _accept_quest_offer(
        self,
        session: GameSession,
        offer: Dict[str, Any],
        giver_entity_id: Optional[str] = None,
        giver_name: Optional[str] = None,
    ) -> Optional[str]:
        quest_id = offer.get("id")
        if not quest_id or session.quest_tracker.get_quest(quest_id):
            return None
        current_hour = self._current_game_hour(session)
        deadline_hours = offer.get("deadline_hours")
        deadline_hour = current_hour + deadline_hours if deadline_hours else None
        session.quest_tracker.add_quest(
            quest_id=quest_id,
            title=offer.get("title", quest_id.replace("_", " ").title()),
            current_hour=current_hour,
            deadline_hour=deadline_hour,
            timeout_consequence=offer.get("timeout_consequence", "quest_failed"),
        )
        quest_meta = copy.deepcopy(offer)
        quest_meta["giver_entity_id"] = giver_entity_id
        quest_meta["giver_name"] = giver_name
        session.campaign_state.setdefault("quest_meta", {})[quest_id] = quest_meta
        accepted_quests = session.campaign_state.setdefault("accepted_quests", [])
        if quest_id not in accepted_quests:
            accepted_quests.append(quest_id)
        return quest_id

    def _update_quest_progress_for_kill(self, session: GameSession, enemy_name: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        quest_meta = session.campaign_state.get("quest_meta", {})
        progress = session.campaign_state.setdefault("quest_progress", {})
        current_hour = self._current_game_hour(session)
        for quest in session.quest_tracker.get_active_quests():
            meta = quest_meta.get(quest.quest_id, {})
            if meta.get("kind") != "hunt":
                continue
            target_name = str(meta.get("target_name", "")).lower()
            if target_name and target_name not in enemy_name.lower():
                continue
            progress[quest.quest_id] = int(progress.get(quest.quest_id, 0)) + 1
            required_kills = int(meta.get("required_kills", 1))
            if progress[quest.quest_id] >= required_kills:
                session.quest_tracker.complete_quest(quest.quest_id, current_hour)
                reward_gold = int(meta.get("reward_gold", 40))
                reward_xp = int(meta.get("reward_xp", 60))
                session.player.gold += reward_gold
                self.progression.add_xp(session.player, reward_xp)
                completed = session.campaign_state.setdefault("completed_quests", [])
                if quest.quest_id not in completed:
                    completed.append(quest.quest_id)
                completed_ids = session.campaign_state.setdefault("completed_quest_ids", [])
                if quest.quest_id not in completed_ids:
                    completed_ids.append(quest.quest_id)
                accepted = session.campaign_state.setdefault("accepted_quests", [])
                if quest.quest_id in accepted:
                    accepted.remove(quest.quest_id)
                events.append({
                    "type": "quest_complete",
                    "quest_id": quest.quest_id,
                    "title": quest.title,
                    "reward_gold": reward_gold,
                    "reward_xp": reward_xp,
                })
        return events

    def _generate_emergent_quests(self, session: GameSession, force: bool = False) -> List[Dict[str, Any]]:
        offers: List[Dict[str, Any]] = []
        existing_quests = set(session.quest_tracker.quests.keys())
        shortage_specs = [
            ("bread", "Bread Shortage", "The taverns need fresh bread before tonight.", 2, 20, 35),
            ("ale", "Dry Casks", "Cellars are running low on ale. Bring stock before evening trade.", 2, 18, 35),
            ("healing_potion", "Remedy Run", "The local healer is running short on remedies.", 1, 24, 50),
        ]
        for item_id, title, description, qty, deadline, reward in shortage_specs:
            baseline = session.location_stock.baseline.get(item_id, 0)
            stock = session.location_stock.get_stock(item_id)
            quest_id = f"resupply_{item_id}"
            if quest_id in existing_quests:
                continue
            if force or (baseline and stock <= max(1, baseline // 3)):
                offers.append({
                    "id": quest_id,
                    "kind": "delivery",
                    "title": title,
                    "description": description,
                    "target_item": item_id,
                    "required_qty": qty,
                    "deadline_hours": deadline,
                    "reward_gold": reward,
                    "reward_xp": 40,
                    "source": "emergent",
                })

        hunt_id = "clear_the_roads"
        if hunt_id not in existing_quests and (force or "road" in session.dm_context.location.lower() or "forest" in session.dm_context.location.lower()):
            offers.append({
                "id": hunt_id,
                "kind": "hunt",
                "title": "Clear The Roads",
                "description": "Predators and raiders have made the roads unsafe. Cut them down.",
                "target_name": "goblin",
                "required_kills": 2,
                "deadline_hours": 36,
                "reward_gold": 60,
                "reward_xp": 75,
                "source": "emergent",
            })

        return offers[:3]
