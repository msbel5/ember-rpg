"""GameEngine mixin for session creation and living-world orchestration."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.api.game_session import GameSession
from engine.api.runtime_constants import CLASS_ALIASES, DEFAULT_PLAYER_CLASS, LOCATION_STOCK_BASELINE, OPENING_SCENES, STARTER_KITS
from engine.core.character import Character
from engine.core.character_creation import (
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
)
from engine.core.dm_agent import DMContext, SceneType
from engine.data_loader import get_class_default_hp, get_class_default_spell_points, get_class_default_stats
from engine.world.behavior_tree import BehaviorContext, create_npc_behavior_tree
from engine.world.economy import LocationStock
from engine.world.entity import EntityType
from engine.world.ethics import FACTION_ETHICS, get_faction_context
from engine.world.history import HistorySeed
from engine.world.naming import NameGenerator
from engine.world.npc_needs import NPCNeeds
from engine.world.schedules import NPCSchedule


class GameEngineRuntimeMixin:
    """Focused GameEngine behavior for session setup and world ticking."""

    def new_session(
        self,
        player_name: str,
        player_class: str = DEFAULT_PLAYER_CLASS,
        location: Optional[str] = None,
        *,
        alignment: Optional[str] = None,
        skill_proficiencies: Optional[List[str]] = None,
        stats: Optional[Dict[str, int]] = None,
        creation_answers: Optional[List[Dict[str, Any]]] = None,
        creation_profile: Optional[Dict[str, Any]] = None,
    ) -> GameSession:
        requested_class = str(player_class or DEFAULT_PLAYER_CLASS).lower()
        player_class = CLASS_ALIASES.get(requested_class, requested_class)
        class_stats_template = get_class_default_stats(player_class)
        unknown_class = not class_stats_template
        if unknown_class:
            player_class = DEFAULT_PLAYER_CLASS
            class_stats_template = get_class_default_stats(player_class)
        assigned_stats = dict(stats or {})
        if assigned_stats:
            for key in ("MIG", "AGI", "END", "MND", "INS", "PRE"):
                assigned_stats.setdefault(key, 10)
        else:
            assigned_stats = dict(class_stats_template)
        hp = 16 if unknown_class else get_class_default_hp(player_class)
        sp = get_class_default_spell_points(player_class)

        creation_profile = dict(creation_profile or {})
        recommended_axes = dict(creation_profile.get("alignment_axes") or {})
        effective_alignment = alignment or recommended_alignment_from_axes(recommended_axes) if recommended_axes else (alignment or "TN")
        default_skills = recommended_skills_for_class({"skill_weights": creation_profile.get("skill_weights", {})}, player_class)
        selected_skills = list(skill_proficiencies or default_skills or CLASS_DEFAULT_SKILLS.get(player_class, []))
        allowed_skills = set(CLASS_SKILL_OPTIONS.get(player_class, []))
        selected_skills = [skill for skill in selected_skills if skill in allowed_skills][: CLASS_SKILL_COUNTS.get(player_class, 2)]
        if len(selected_skills) < CLASS_SKILL_COUNTS.get(player_class, 2):
            for fallback in CLASS_DEFAULT_SKILLS.get(player_class, []):
                if fallback in allowed_skills and fallback not in selected_skills:
                    selected_skills.append(fallback)
                if len(selected_skills) >= CLASS_SKILL_COUNTS.get(player_class, 2):
                    break

        player = Character(
            name=player_name,
            classes={player_class: 1},
            stats=assigned_stats,
            hp=hp,
            max_hp=hp,
            spell_points=sp,
            max_spell_points=sp,
            level=1,
            xp=0,
            skill_proficiencies=selected_skills,
            alignment=effective_alignment or "TN",
            creation_answers=list(creation_answers or []),
            creation_profile=creation_profile,
            use_death_saves=True,
        )
        player.set_alignment_from_axes() if not alignment and recommended_axes else None
        player.sync_derived_progression()

        loc = OPENING_SCENES[0][0] if location is None else location
        dm_context = DMContext(scene_type=SceneType.EXPLORATION, location=loc, party=[player])
        session = GameSession(player=player, dm_context=dm_context)

        seed = hash(session.session_id) % 1000000
        session.history_seed = HistorySeed().generate(seed=seed)
        session.name_gen = NameGenerator(seed=seed)

        hp_scale = player.max_hp / 20.0
        for part in session.body_tracker.max_hp:
            session.body_tracker.max_hp[part] = max(1, int(session.body_tracker.max_hp[part] * hp_scale))
            session.body_tracker.current_hp[part] = session.body_tracker.max_hp[part]

        session.location_stock = LocationStock(location_id=loc.lower().replace(" ", "_"), baseline=LOCATION_STOCK_BASELINE)
        self._populate_scene_entities(session, loc)

        kit = STARTER_KITS.get(player_class.lower(), STARTER_KITS[DEFAULT_PLAYER_CLASS])
        for item_template in kit:
            item = dict(item_template)
            slot = item.get("slot")
            if slot and session.equipment.get(slot) is None:
                session.set_equipment_slot(slot, item)
                if slot == "armor" and session.ap_tracker:
                    material = item.get("material", "none")
                    armor_weight_map = {
                        "cloth": "cloth",
                        "leather": "leather",
                        "iron": "chain_mail",
                        "steel": "plate_armor",
                    }
                    session.ap_tracker.set_armor(armor_weight_map.get(material, "none"))
            else:
                session.add_item(item)

        session.quest_offers = GameSession.merge_quest_offers(
            session.quest_offers,
            self._generate_emergent_quests(session, force=True),
            new_default_source="emergent",
        )
        session.narration_context["last_world_tick_hour"] = self._current_game_hour(session)
        session.ensure_consistency()
        return session

    def _world_tick(self, session: GameSession, minutes: int = 15, refresh_ap: bool = False) -> list:
        events: List[Dict[str, Any]] = []
        if not getattr(session, "game_time", None):
            return events

        remaining_minutes = max(0, int(minutes))
        if remaining_minutes == 0:
            return events

        world_period_changed = False
        final_hour = self._current_game_hour(session)
        step_size = 15

        while remaining_minutes > 0:
            step_minutes = min(step_size, remaining_minutes)
            before_hour = self._current_game_hour(session)
            previous_period = session.game_time.period
            session.game_time.advance(step_minutes)
            session.clear_expired_timed_conditions()
            after_hour = self._current_game_hour(session)
            final_hour = after_hour
            hours_passed = step_minutes / 60.0
            current_period = session.game_time.period
            world_period_changed = world_period_changed or (previous_period != current_period)

            for entity_id, entity in session.entities.items():
                needs = entity.get("needs")
                if isinstance(needs, NPCNeeds):
                    needs.tick(hours=hours_passed)
                schedule = entity.get("schedule")
                if isinstance(schedule, NPCSchedule):
                    entity["scheduled_location"] = schedule.get_location(current_period)

            if session.spatial_index:
                npc_entities = session.spatial_index.entities_of_type(EntityType.NPC)
                for npc in npc_entities:
                    if npc.id == "player" or not npc.is_alive():
                        continue
                    if session.entity_position_locked(npc.id):
                        if npc.id in session.entities:
                            session.sync_entity_record(npc.id, npc)
                        continue
                    tree = create_npc_behavior_tree(is_guard=(npc.job == "guard"))
                    hostiles = [session.player_entity] if npc.is_hostile() and session.player_entity else []
                    ctx = BehaviorContext(
                        entity=npc,
                        spatial_index=session.spatial_index,
                        game_time=session.game_time,
                        map_data=session.map_data,
                        hostiles=hostiles,
                    )
                    tree.tick(ctx)
                    action_type = ctx.blackboard.get("action")
                    target_pos = ctx.blackboard.get("target_pos")

                    if action_type == "follow_schedule" and isinstance(npc.schedule, NPCSchedule):
                        scheduled_pos = npc.schedule.get_position(current_period)
                        if scheduled_pos:
                            target_pos = tuple(scheduled_pos)

                    if target_pos and action_type in {"wander", "flee", "patrol", "move_toward_hostile", "follow_schedule"}:
                        target_pos = tuple(target_pos)
                        step_target = self._step_toward(tuple(npc.position), target_pos)
                        moved = self._move_entity_if_possible(session, npc, step_target)
                        if moved:
                            if npc.id in session.entities:
                                session.sync_entity_record(npc.id, npc)
                            destination = (
                                getattr(npc.schedule, "get_location", lambda _period: "their post")(current_period)
                                if action_type == "follow_schedule"
                                else action_type.replace("_", " ")
                            )
                            events.append(
                                {
                                    "type": "npc_move",
                                    "npc_id": npc.id,
                                    "npc_name": npc.name,
                                    "position": [npc.position[0], npc.position[1]],
                                    "destination": destination,
                                }
                            )

            crossed_hours = list(range(int(before_hour) + 1, int(after_hour) + 1))
            for hour_marker in crossed_hours:
                if session.ap_tracker is not None and refresh_ap:
                    session.ap_tracker.refresh()
                elif session.ap_tracker is not None:
                    session.ap_tracker.refresh()
                self._run_hourly_world_updates(session, hour_marker, events)
                quest_result = session.quest_tracker.tick(float(hour_marker))
                expired = list(quest_result.get("expired") or [])
                reminders = list(quest_result.get("reminders") or [])
                if expired:
                    failed = session.campaign_state.setdefault("failed_quests", [])
                    failed_ids = session.campaign_state.setdefault("failed_quest_ids", [])
                    accepted = session.campaign_state.setdefault("accepted_quests", [])
                    for event in expired:
                        quest_id = event.get("quest_id")
                        if quest_id and quest_id not in failed:
                            failed.append(quest_id)
                        if quest_id and quest_id not in failed_ids:
                            failed_ids.append(quest_id)
                        if quest_id in accepted:
                            accepted.remove(quest_id)
                    events.extend(expired)
                if reminders:
                    events.extend(reminders)

            if crossed_hours:
                session.quest_offers = GameSession.merge_quest_offers(
                    session.quest_offers,
                    self._generate_emergent_quests(session),
                    new_default_source="emergent",
                )
            remaining_minutes -= step_minutes

        session.campaign_state["last_world_tick_hour"] = final_hour
        session.narration_context["world_period_changed"] = world_period_changed
        return events

    def _build_world_context(self, session: GameSession) -> str:
        parts = []
        if session.game_time:
            parts.append(f"[Time: {session.game_time.to_string()}]")

        nearby = []
        for entity_id, entity in session.entities.items():
            if str(entity.get("type", "npc")).lower() != "npc":
                continue
            ent_pos = entity.get("position", [0, 0])
            dist = max(abs(session.position[0] - ent_pos[0]), abs(session.position[1] - ent_pos[1]))
            if dist <= 3:
                needs = entity.get("needs")
                mood = needs.emotional_state() if isinstance(needs, NPCNeeds) else "content"
                name = entity.get("name", entity_id)
                role = entity.get("role", "npc")
                faction = entity.get("faction", "independent")
                nearby.append(f"  {name} ({role}, {faction}) — mood: {mood}")
        if nearby:
            parts.append("[Nearby NPCs]\n" + "\n".join(nearby))

        factions_seen = set()
        for entity in session.entities.values():
            faction = entity.get("faction", "")
            if faction and faction in FACTION_ETHICS and faction not in factions_seen:
                factions_seen.add(faction)
                context = get_faction_context(faction)
                parts.append(f"[Faction: {faction}] Values: {', '.join(context['top_values'])}. Personality: {context['personality']}")

        if session.history_seed:
            tensions = session.history_seed.get_tensions()
            if tensions:
                parts.append("[Current Tensions] " + "; ".join(tension.name for tension in tensions[:3]))

        active_rumors = session.rumor_network.get_all_active()
        if active_rumors:
            parts.append("[Rumors] " + "; ".join(f"'{rumor.fact}' (confidence: {rumor.confidence:.0%})" for rumor in active_rumors[:3]))

        price_notes = []
        for item in ["food", "iron_bar", "healing_potion"]:
            modifier = session.location_stock.get_price_modifier(item)
            if modifier != 1.0:
                price_notes.append(f"{item}: {modifier:.1f}x price")
        if price_notes:
            parts.append("[Economy] " + ", ".join(price_notes))

        active_quests = session.quest_tracker.get_active_quests()
        if active_quests:
            quest_strings = [
                f"'{quest.title}'" + (f" (deadline in {quest.deadline_hour - (session.game_time.hour + (session.game_time.day - 1) * 24):.0f}h)" if quest.deadline_hour else "")
                for quest in active_quests[:3]
            ]
            parts.append("[Active Quests] " + "; ".join(quest_strings))
        elif session.quest_offers:
            offer_strings = [f"'{offer['title']}'" for offer in session.quest_offers[:2] if offer.get("title")]
            if offer_strings:
                parts.append("[Quest Leads] " + "; ".join(offer_strings))

        injuries = session.body_tracker.get_injury_effects()
        if injuries:
            parts.append("[Player Injuries] " + ", ".join(f"{part}: {status}" for part, status in injuries.items()))

        return "\n".join(parts)
