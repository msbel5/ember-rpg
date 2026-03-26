"""Dialogue and social action handlers."""
from __future__ import annotations

from engine.api.action_parser import ActionIntent, ParsedAction
from engine.api.game_session import GameSession
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.data_loader import list_npc_templates
from engine.world.npc_needs import NPCNeeds

from engine.api.runtime_constants import THINK_TOPIC_SKILLS


class SocialActionsMixin:
    """Focused social handlers for talking, influence, and trade flows."""

    def _handle_talk(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or "a stranger"
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "talk")
        if ap_fail:
            return ap_fail

        npc_personality = self._get_npc_personality(target)
        npc_id = target.lower().replace(" ", "_")
        prior_context = {}
        found_entity = self._find_entity_by_name(session, target)
        npc_mood = "content"
        quest_offer_note = ""
        resolved_name = target
        attitude = "indifferent"
        if found_entity:
            npc_id, entity = found_entity
            resolved_name = entity.get("name", target)
            attitude = self._entity_attitude(entity)
            memory = session.npc_memory.get_memory(npc_id, npc_name=resolved_name)
            if memory and len(memory.conversations) > 0:
                prior_context["prior_interactions"] = len(memory.conversations)
                prior_context["npc_memory_summary"] = memory.build_context()
            needs = entity.get("needs")
            if isinstance(needs, NPCNeeds):
                npc_mood = needs.emotional_state()
                npc_behavior = needs.behavior_modifiers()
                if not npc_behavior.get("will_talk", True):
                    return ActionResult(
                        narrative=f"{entity['name']} looks too anxious to talk right now. Their eyes dart around nervously.",
                        scene_type=session.dm_context.scene_type,
                    )
            if entity.get("role") in {"quest_giver", "guard", "merchant"} and session.quest_offers:
                session.narration_context["last_quest_giver_id"] = npc_id
                session.narration_context["last_quest_giver_name"] = resolved_name
                session.narration_context["last_shown_quest_offer_ids"] = [offer.get("id") for offer in session.quest_offers[:3]]
                offer_lines = [f"- {offer['title']}: {offer.get('description', '').strip()}" for offer in session.quest_offers[:2] if offer.get("title")]
                if offer_lines:
                    quest_offer_note = "\nAvailable quests:\n" + "\n".join(offer_lines) + "\nAccept with 'accept quest <title>'."
        else:
            memory = session.npc_memory.get_memory(npc_id, npc_name=resolved_name)
            if memory and len(memory.conversations) > 0:
                prior_context["prior_interactions"] = len(memory.conversations)
                prior_context["npc_memory_summary"] = memory.build_context()

        world_context = self._build_world_context(session)
        event = DMEvent(
            type=EventType.DIALOGUE,
            description=(
                f"{session.player.name} approaches {resolved_name} to speak. "
                f"{session.player.name} says: (initiate conversation). "
                f"Generate {resolved_name}'s response as they would actually speak, "
                f"in character with their personality.\n"
                f"NPC mood: {npc_mood}.\n"
                f"NPC attitude: {attitude}.\n"
                f"{world_context}"
            ),
            data={
                "player_name": session.player.name,
                "location": session.dm_context.location,
                "npc_name": resolved_name,
                "npc_personality": npc_personality,
                "npc_mood": npc_mood,
                "action": "talk",
                "player_input": action.raw_input,
                "world_context": world_context,
                **prior_context,
            },
        )
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        session.set_conversation_target("npc", npc_id=npc_id, npc_name=resolved_name)
        self._hold_interaction_target(session, npc_id, "talk")

        memory_time = session.game_time.to_string() if session.game_time else "Day 1, 08:00 (morning)"
        session.npc_memory.record_interaction(
            npc_id,
            action.raw_input[:200],
            "neutral",
            memory_time,
            facts=[f"Attitude: {attitude}", f"Conversation target: {resolved_name}"],
        )
        self._record_eavesdroppers(session, npc_id, action.raw_input[:200])
        return ActionResult(narrative=f"{narrative}{quest_offer_note}", scene_type=session.dm_context.scene_type)

    def _handle_address(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or session.conversation_state.get("npc_name")
        if not target:
            session.set_conversation_target("dm")
            return self._handle_unknown(session, ParsedAction(ActionIntent.UNKNOWN, action.raw_input))
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            session.clear_conversation_target()
            return prox_fail
        ap_fail = self._check_ap(session, "talk")
        if ap_fail:
            return ap_fail
        found = self._find_entity_by_name(session, target)
        if found is None:
            session.clear_conversation_target()
            return ActionResult(
                narrative=f"{target} is no longer close enough to hear you.",
                scene_type=session.dm_context.scene_type,
            )
        npc_id, entity = found
        resolved_name = entity.get("name", target)
        session.set_conversation_target("npc", npc_id=npc_id, npc_name=resolved_name)
        self._hold_interaction_target(session, npc_id, "address")
        memory_time = session.game_time.to_string() if session.game_time else "Day 1, 08:00 (morning)"
        session.npc_memory.record_interaction(
            npc_id,
            action.raw_input[:200],
            "neutral",
            memory_time,
            facts=[f"Conversation target: {resolved_name}"],
        )
        self._record_eavesdroppers(session, npc_id, action.raw_input[:200])
        event = DMEvent(
            type=EventType.DIALOGUE,
            description=f"{session.player.name} says to {resolved_name}: {action.raw_input}",
            data={
                "player_name": session.player.name,
                "npc_name": resolved_name,
                "player_input": action.raw_input,
                "conversation_target": resolved_name,
                "world_context": self._build_world_context(session),
            },
        )
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_think(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        topic = (action.target or action.action_detail or "your situation").strip()
        ap_fail = self._check_ap(session, "examine")
        if ap_fail:
            return ap_fail
        session.set_conversation_target("self", npc_name="self")
        lowered = topic.lower()
        chosen_skill = "history"
        for skill, keywords in THINK_TOPIC_SKILLS.items():
            if any(keyword in lowered for keyword in keywords):
                chosen_skill = skill
                break
        dc = 5 if any(word in lowered for word in ("town", "road", "guard", "merchant", "common", "bread")) else 15
        if any(word in lowered for word in ("secret", "cult", "artifact", "true name", "gizli", "sır")):
            dc = 25
        result = self._roll_player_skill_check(session, chosen_skill, dc)
        check_text = self._format_skill_check(result, chosen_skill.title(), dc)
        deterministic = (
            f"You think through what you know about {topic}. Fragments of {chosen_skill} knowledge align into a useful conclusion."
            if result.success
            else f"You search your memory about {topic}, but nothing certain comes to mind."
        )
        return ActionResult(narrative=f"{check_text}\n{deterministic}", scene_type=session.dm_context.scene_type)

    def _handle_persuade(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or "someone"
        found = self._find_entity_by_name(session, target)
        if found is None:
            return ActionResult(
                narrative="There's no one here by that name.",
                scene_type=session.dm_context.scene_type,
            )
        entity_id, entity = found
        target = entity.get("name", target)
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "persuade")
        if ap_fail:
            return ap_fail

        dc = self._social_dc(entity, "minor_risk")
        check_result = self._roll_player_skill_check(session, "persuasion", dc)
        check_text = self._format_skill_check(check_result, "Persuasion", dc)
        if check_result.success:
            narrative = f"Your words ring true and {target} seems persuaded."
            self._shift_attitude_step(session, entity_id, +1)
        else:
            narrative = f"{target} remains unconvinced by your plea."
        self._hold_interaction_target(session, entity_id, "social")

        event = DMEvent(
            type=EventType.DIALOGUE,
            description=f"{session.player.name} tries to persuade {target}. {'Succeeds' if check_result.success else 'Fails'}.",
            data={
                "player_name": session.player.name,
                "action": "persuade",
                "target": target,
                "success": check_result.success,
            },
        )
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_intimidate(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or "someone"
        found = self._find_entity_by_name(session, target)
        if found is None:
            return ActionResult(
                narrative="There's no one here by that name.",
                scene_type=session.dm_context.scene_type,
            )
        entity_id, entity = found
        target = entity.get("name", target)
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "intimidate")
        if ap_fail:
            return ap_fail

        advantage = self._get_player_ability(session, "MIG") >= int((entity.get("stats") or {}).get("MIG", 10))
        npc_insight = 10 + self._npc_skill_bonus(entity, "insight")
        check_result = self._roll_player_skill_check(session, "intimidation", npc_insight, advantage=advantage)
        check_text = self._format_skill_check(check_result, "Intimidation", npc_insight)
        if check_result.success:
            narrative = f"{target} cowers before your menacing presence."
            self._set_entity_attitude(session, entity_id, "hostile")
        else:
            narrative = f"{target} stands firm, unimpressed by your threats."
        self._hold_interaction_target(session, entity_id, "social")

        event = DMEvent(
            type=EventType.DIALOGUE,
            description=f"{session.player.name} tries to intimidate {target}.",
            data={
                "player_name": session.player.name,
                "action": "intimidate",
                "target": target,
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_bribe(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        import re

        raw_target = action.target or session.conversation_state.get("npc_name") or "someone"
        gift_value = next((int(token) for token in raw_target.split() if token.isdigit()), 10)
        target = re.sub(r"\s*\d+\s*(?:gold|gp|altın)?\s*$", "", raw_target, flags=re.IGNORECASE).strip() or raw_target
        found = self._find_entity_by_name(session, target)
        if found is None:
            return ActionResult(
                narrative="There's no one here by that name.",
                scene_type=session.dm_context.scene_type,
            )
        entity_id, entity = found
        target = entity.get("name", target)
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "bribe")
        if ap_fail:
            return ap_fail
        if session.player.gold < gift_value:
            return ActionResult(
                narrative=f"You do not have {gift_value} gold to offer as a bribe.",
                scene_type=session.dm_context.scene_type,
            )
        susceptibility = 1.0
        needs = entity.get("needs")
        if isinstance(needs, NPCNeeds):
            susceptibility = 1.0 + float(needs.behavior_modifiers().get("bribe_susceptibility", 0.0))
        dc = max(5, int(self._social_dc(entity, "minor_risk") - (gift_value / 10.0) * susceptibility))
        check_result = self._roll_player_skill_check(session, "persuasion", dc)
        check_text = self._format_skill_check(check_result, "Bribe", dc)
        session.player.gold -= gift_value
        self._hold_interaction_target(session, entity_id, "social")
        if check_result.success:
            new_attitude = self._shift_attitude_step(session, entity_id, +1)
            narrative = f"You quietly offer {gift_value} gold. {target} accepts and softens to {new_attitude}."
        else:
            narrative = f"{target} eyes the coin, but the offer fails to sway them."
        return ActionResult(narrative=f"{check_text}\n{narrative}", scene_type=session.dm_context.scene_type)

    def _handle_deceive(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or session.conversation_state.get("npc_name") or "someone"
        found = self._find_entity_by_name(session, target)
        if found is None:
            return ActionResult(
                narrative="There's no one here by that name.",
                scene_type=session.dm_context.scene_type,
            )
        entity_id, entity = found
        target = entity.get("name", target)
        prox_fail = self._check_entity_proximity(session, target, "social")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "persuade")
        if ap_fail:
            return ap_fail
        passive_insight = 10 + self._npc_skill_bonus(entity, "insight")
        check_result = self._roll_player_skill_check(session, "deception", passive_insight)
        check_text = self._format_skill_check(check_result, "Deception", passive_insight)
        self._hold_interaction_target(session, entity_id, "social")
        if check_result.success:
            narrative = f"Your lie lands cleanly. {target} seems to believe you."
            self._apply_alignment_shift(session, law_delta=-3, good_delta=-2)
        else:
            narrative = f"{target} narrows their eyes. They do not believe your story."
            if entity_id:
                self._shift_attitude_step(session, entity_id, -1)
            self._apply_alignment_shift(session, law_delta=-5, good_delta=-4)
        return ActionResult(narrative=f"{check_text}\n{narrative}", scene_type=session.dm_context.scene_type)

    def _handle_trade(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or "a merchant"
        prox_fail = self._check_entity_proximity(session, target, "trade")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "trade")
        if ap_fail:
            return ap_fail

        found_entity = self._find_entity_by_name(session, target)
        if found_entity:
            entity_id, entity = found_entity
            needs = entity.get("needs")
            if isinstance(needs, NPCNeeds):
                behavior = needs.behavior_modifiers()
                if not behavior.get("will_trade", True):
                    return ActionResult(
                        narrative=f"{entity['name']} shakes their head. 'Not now. Too dangerous to do business.'",
                        scene_type=session.dm_context.scene_type,
                    )
            session.set_conversation_target("npc", npc_id=entity_id, npc_name=entity.get("name", target))
            self._hold_interaction_target(session, entity_id, "trade")

        npc_personality = self._get_npc_personality(target)
        price_info = []
        for item in ["food", "ale", "iron_bar", "healing_potion", "bread"]:
            stock = session.location_stock.get_stock(item)
            price = session.location_stock.get_effective_price(item)
            if stock > 0:
                price_info.append(f"{item}: {stock} in stock, {price:.1f}g each")
        stock_str = "; ".join(price_info) if price_info else "Limited stock available"
        world_context = self._build_world_context(session)
        event = DMEvent(
            type=EventType.DIALOGUE,
            description=(
                f"{session.player.name} wants to trade with {target}. "
                f"Generate {target}'s response showing their wares and willingness to trade.\n"
                f"Available stock: {stock_str}\n"
                f"{world_context}"
            ),
            data={
                "player_name": session.player.name,
                "location": session.dm_context.location,
                "npc_name": target,
                "npc_personality": npc_personality,
                "action": "trade",
                "player_input": action.raw_input,
                "stock_info": stock_str,
                "world_context": world_context,
            },
        )
        self.dm.transition(session.dm_context, SceneType.DIALOGUE)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _get_npc_personality(self, target_name: str) -> dict:
        target_lower = target_name.lower()
        for npc in list_npc_templates():
            if (
                target_lower in npc.get("name", "").lower()
                or target_lower in npc.get("id", "").lower()
                or target_lower in npc.get("role", "").lower()
            ):
                return {
                    "name": npc.get("name"),
                    "role": npc.get("role"),
                    "personality": npc.get("personality", []),
                    "speech_style": npc.get("speech_style"),
                    "greeting": npc.get("dialogue", {}).get("greeting", []),
                }
        return {}
