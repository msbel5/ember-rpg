"""Campaign-first runtime built on top of the world simulation kernel."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Callable, Optional

from engine.api.campaign.debug_trace import snapshot_hash, trace_event
from engine.api.game_engine import GameEngine
from engine.api.save_system import SaveSystem
from engine.kernel.creation import ABILITY_ORDER, CreationState, assign_stats_to_class
from engine.kernel import GameState
from engine.worldgen import WorldSeed, initialize_simulation, load_world_snapshot, realize_region, tick_global

from .context import CampaignContext, CampaignCreationContext
from .controls import merge_settlement_controls
from .dialog import build_dialog_payload
from .live_kernel import advance_kernel_runtime, ensure_kernel_runtime
from .persistence import campaign_payload, persist_campaign_state
from .session import apply_region_to_session
from .settlement import build_character_sheet, build_settlement_state
from .world import (
    alerts_from_events,
    build_world,
    choose_starting_settlement,
    derive_creation_world_seed,
    region_payload,
)
from ..campaign_commands import (
    handle_travel,
    hours_for_avatar_command,
    maybe_handle_commander_command,
    merge_avatar_narrative,
    resolve_command_text,
)


class CampaignRuntime:
    """Owns campaign-first lifecycle, command dispatch, and save/load."""

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        self.engine = GameEngine(llm=llm)
        self.save_system = SaveSystem()
        self._campaigns: dict[str, CampaignContext] = {}
        self._creation_flows: dict[str, CampaignCreationContext] = {}

    def create_campaign(
        self,
        player_name: str,
        player_class: str = "warrior",
        adapter_id: str = "fantasy_ember",
        profile_id: str = "standard",
        seed: Optional[int] = None,
        *,
        alignment: Optional[str] = None,
        skill_proficiencies: Optional[list[str]] = None,
        stats: Optional[dict[str, int]] = None,
        creation_answers: Optional[list[dict[str, Any]]] = None,
        creation_profile: Optional[dict[str, Any]] = None,
    ) -> CampaignContext:
        requested_seed = seed if seed is not None else int(WorldSeed(f"{player_name}:{adapter_id}:{profile_id}"))
        chosen_seed = derive_creation_world_seed(
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=requested_seed,
            creation_profile=creation_profile,
            creation_answers=creation_answers,
        )
        world = build_world(adapter_id=adapter_id, profile_id=profile_id, seed=chosen_seed)
        settlement = choose_starting_settlement(
            world,
            creation_profile=creation_profile,
            creation_answers=creation_answers,
        ) or world.settlements[0]
        initialize_simulation(world, settlement.region_id)
        region_snapshot = realize_region(world, settlement.region_id)
        session = self.engine.new_session(
            player_name=player_name,
            player_class=player_class,
            location=settlement.center_name,
            alignment=alignment,
            skill_proficiencies=skill_proficiencies,
            stats=stats,
            creation_answers=creation_answers,
            creation_profile=creation_profile,
        )
        settlement_state = build_settlement_state(world, region_snapshot, adapter_id, player_name)
        campaign_id = str(uuid.uuid4())
        apply_region_to_session(
            session=session,
            world=world,
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            campaign_id=campaign_id,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=chosen_seed,
        )
        opening = (
            f"{player_name} enters {settlement.center_name}, a {adapter_id.replace('_', ' ')} frontier "
            f"settlement shaped by {region_snapshot.metadata.get('explainability', {}).get('terrain_driver', 'local forces')}."
        )
        context = CampaignContext(
            campaign_id=campaign_id,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=chosen_seed,
            world=world,
            session=session,
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            recent_event_log=[{"event_type": "campaign_start", "summary": opening}],
        )
        ensure_kernel_runtime(context)
        self._campaigns[campaign_id] = context
        persist_campaign_state(context)
        return context

    def start_creation(
        self,
        *,
        player_name: str,
        adapter_id: str = "fantasy_ember",
        profile_id: str = "standard",
        seed: Optional[int] = None,
        location: Optional[str] = None,
    ) -> CampaignCreationContext:
        chosen_seed = seed if seed is not None else int(WorldSeed(f"{player_name}:{adapter_id}:{profile_id}:creation"))
        state = CreationState(player_name=player_name, location=location, rng_seed=chosen_seed)
        state.ensure_roll()
        context = CampaignCreationContext(
            state=state,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=chosen_seed,
            location=location,
        )
        self._creation_flows[state.creation_id] = context
        return context

    def get_creation(self, creation_id: str) -> CampaignCreationContext:
        context = self._creation_flows.get(creation_id)
        if context is None:
            raise KeyError(creation_id)
        return context

    def answer_creation(self, creation_id: str, question_id: str, answer_id: str) -> CampaignCreationContext:
        context = self.get_creation(creation_id)
        context.state.answer_question(question_id, answer_id)
        return context

    def reroll_creation(self, creation_id: str) -> CampaignCreationContext:
        context = self.get_creation(creation_id)
        context.state.reroll()
        return context

    def save_creation_roll(self, creation_id: str) -> CampaignCreationContext:
        context = self.get_creation(creation_id)
        context.state.save_current_roll()
        return context

    def swap_creation_roll(self, creation_id: str) -> CampaignCreationContext:
        context = self.get_creation(creation_id)
        context.state.swap_rolls()
        return context

    def finalize_creation(
        self,
        creation_id: str,
        *,
        player_name: Optional[str] = None,
        adapter_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        seed: Optional[int] = None,
        player_class: Optional[str] = None,
        alignment: Optional[str] = None,
        skill_proficiencies: Optional[list[str]] = None,
        assigned_stats: Optional[dict[str, int]] = None,
        selected_facets: Optional[dict[str, Any]] = None,
        creation_answers: Optional[list[dict[str, Any]]] = None,
        creation_profile: Optional[dict[str, Any]] = None,
        location: Optional[str] = None,
    ) -> CampaignContext:
        creation_context = self.get_creation(creation_id)
        state = creation_context.state
        effective_player_name = str(player_name or state.player_name or "Adventurer")
        effective_adapter_id = str(adapter_id or creation_context.adapter_id or "fantasy_ember")
        effective_profile_id = str(profile_id or creation_context.profile_id or "standard")
        effective_seed = seed if seed is not None else creation_context.seed
        effective_class = str(player_class or state.recommended_class() or "warrior").lower()
        effective_alignment = alignment or state.recommended_alignment()
        effective_skills = list(skill_proficiencies or state.recommended_skills(effective_class))
        effective_stats, stat_source = self._resolve_assigned_stats(state, effective_class, assigned_stats)
        merged_creation_profile = {
            "class_weights": dict(state.class_weights),
            "skill_weights": dict(state.skill_weights),
            "alignment_axes": dict(state.alignment_axes),
            "recommended_class": state.recommended_class(),
            "recommended_alignment": state.recommended_alignment(),
            "recommended_skills": state.recommended_skills(effective_class),
            "rolled_values": list(state.current_roll),
            "saved_roll": list(state.saved_roll) if state.saved_roll is not None else None,
            "facet_scores": dict(state.facet_scores),
            "adapter_bias": dict(state.adapter_bias),
            "faction_bias": dict(state.faction_bias),
            "settlement_bias": dict(state.settlement_bias),
            "campaign_genesis": state.campaign_genesis(),
            "world_seed_hints": state.world_seed_hints(),
            "allocation_rules": state.allocation_rules(),
            "selected_facets": dict(selected_facets or {}),
            "stat_source": stat_source,
            "adapter_id": effective_adapter_id,
            "profile_id": effective_profile_id,
            "seed": effective_seed,
            "requested_seed": creation_context.seed,
        }
        merged_creation_profile.update(dict(creation_profile or {}))
        context = self.create_campaign(
            player_name=effective_player_name,
            player_class=effective_class,
            adapter_id=effective_adapter_id,
            profile_id=effective_profile_id,
            seed=effective_seed,
            alignment=effective_alignment,
            skill_proficiencies=effective_skills,
            stats=effective_stats,
            creation_answers=list(creation_answers or state.answers),
            creation_profile=merged_creation_profile,
        )
        if location:
            context.session.dm_context.location = location
        self._creation_flows.pop(creation_id, None)
        persist_campaign_state(context)
        return context

    def get_campaign(self, campaign_id: str) -> CampaignContext:
        context = self._campaigns.get(campaign_id)
        if context is None:
            raise KeyError(campaign_id)
        return context

    def delete_campaign(self, campaign_id: str) -> None:
        self.get_campaign(campaign_id)
        self._campaigns.pop(campaign_id, None)

    def get_current_region(self, campaign_id: str) -> dict[str, Any]:
        return region_payload(self.get_campaign(campaign_id))

    def get_current_settlement(self, campaign_id: str) -> dict[str, Any]:
        return copy.deepcopy(self.get_campaign(campaign_id).settlement_state)

    def build_character_sheet(self, campaign_id: str) -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        return build_character_sheet(context.session, context.settlement_state)

    def save_campaign(
        self,
        campaign_id: str,
        slot_name: Optional[str] = None,
        player_id: Optional[str] = None,
    ) -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        persist_campaign_state(context)
        chosen_player = (player_id or context.session.player.name or "player").strip() or "player"
        chosen_slot = slot_name.strip() if slot_name else f"{campaign_id[:8]}_{context.adapter_id}"
        hashed_snapshot = snapshot_hash(campaign_payload(context))
        self.save_system.save_game(context.session, chosen_slot, player_name=chosen_player)
        trace_event(
            "campaign_save_written",
            campaign_id=context.campaign_id,
            slot_name=chosen_slot,
            snapshot_hash=hashed_snapshot,
        )
        return self.save_system.get_save_metadata(chosen_slot) or {
            "slot_name": chosen_slot,
            "timestamp": "",
            "schema_version": "",
        }

    def list_campaign_saves(self, campaign_id: str) -> list[dict[str, Any]]:
        context = self.get_campaign(campaign_id)
        saves = self.save_system.list_saves(player_name=context.session.player.name)
        return [
            entry
            for entry in saves
            if entry.get("campaign_compatible") and str(entry.get("campaign_id", "")) == context.campaign_id
        ]

    def list_player_campaign_saves(self, player_id: str) -> list[dict[str, Any]]:
        return [
            entry
            for entry in self.save_system.list_saves(player_name=player_id)
            if entry.get("campaign_compatible")
        ]

    def delete_campaign_save(self, save_id: str) -> dict[str, Any]:
        if not self.save_system.delete_save(save_id):
            raise FileNotFoundError(save_id)
        trace_event("campaign_save_deleted", save_id=save_id)
        return {"status": "deleted", "save_id": save_id, "slot_name": save_id}

    def load_campaign(self, save_id: str) -> CampaignContext:
        session = self.save_system.load_game(save_id, strict=True)
        if session is None:
            raise FileNotFoundError(save_id)
        meta = dict(session.campaign_state.get("campaign") or {})
        if not meta:
            trace_event("campaign_save_validation_failed", save_id=save_id, reason="missing_campaign_root")
            raise ValueError(f"Save {save_id} does not contain canonical campaign state")
        if "game_state" in meta:
            GameState.from_dict(dict(meta["game_state"]))
        world = load_world_snapshot(meta["world_snapshot"])
        active_region_id = str(meta.get("active_region_id") or world.simulation_snapshot.active_region_id)
        region_snapshot = realize_region(world, active_region_id)
        settlement_state = copy.deepcopy(
            meta.get("settlement_state")
            or build_settlement_state(world, region_snapshot, str(meta.get("adapter_id", "fantasy_ember")), session.player.name)
        )
        context = CampaignContext(
            campaign_id=str(meta.get("campaign_id", uuid.uuid4())),
            adapter_id=str(meta.get("adapter_id", "fantasy_ember")),
            profile_id=str(meta.get("profile_id", world.profile_id)),
            seed=int(meta.get("seed", world.seed)),
            world=world,
            session=session,
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            recent_event_log=list(meta.get("recent_event_log") or []),
        )
        refreshed_settlement_state = build_settlement_state(world, region_snapshot, context.adapter_id, session.player.name)
        context.settlement_state = merge_settlement_controls(refreshed_settlement_state, settlement_state)
        self._campaigns[context.campaign_id] = context
        apply_region_to_session(
            session=session,
            world=world,
            region_snapshot=region_snapshot,
            settlement_state=context.settlement_state,
            campaign_id=context.campaign_id,
            adapter_id=context.adapter_id,
            profile_id=context.profile_id,
            seed=context.seed,
        )
        ensure_kernel_runtime(context, rebuild_projection=True)
        trace_event(
            "campaign_load_completed",
            campaign_id=context.campaign_id,
            save_id=save_id,
            snapshot_hash=snapshot_hash(campaign_payload(context)),
        )
        return context

    def run_command(
        self,
        campaign_id: str,
        input_text: str,
        shortcut: Optional[str] = None,
        args: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        command_args = dict(args or {})
        issued = resolve_command_text(input_text=input_text, shortcut=shortcut, args=command_args)
        pre_hash = snapshot_hash(campaign_payload(context))
        trace_event(
            "campaign_command_input",
            campaign_id=context.campaign_id,
            command_text=issued,
            shortcut=str(shortcut or ""),
            pre_snapshot_hash=pre_hash,
        )
        lower = issued.lower()
        if lower.startswith("travel"):
            narrative = handle_travel(context, issued, command_args)
            command_type = "travel"
            hours_advanced = int(context.session.campaign_state.get("last_travel_hours", 4))
        else:
            handled = maybe_handle_commander_command(context, issued)
            if handled is not None:
                narrative, command_type, hours_advanced = handled
            else:
                result = self.engine.process_action(context.session, issued)
                narrative = merge_avatar_narrative(context, result.narrative)
                command_type = "avatar"
                hours_advanced = hours_for_avatar_command(lower)

        previous_settlement_state = copy.deepcopy(context.settlement_state)
        tick_result = tick_global(context.world, hours_advanced)
        generated_events = list(tick_result.generated_events)
        active_region_id = str(context.world.simulation_snapshot.active_region_id)
        context.region_snapshot = realize_region(context.world, active_region_id)
        context.settlement_state = build_settlement_state(
            context.world,
            context.region_snapshot,
            context.adapter_id,
            context.session.player.name,
        )
        if command_type != "travel":
            context.settlement_state = merge_settlement_controls(context.settlement_state, previous_settlement_state)
        apply_region_to_session(
            session=context.session,
            world=context.world,
            region_snapshot=context.region_snapshot,
            settlement_state=context.settlement_state,
            campaign_id=context.campaign_id,
            adapter_id=context.adapter_id,
            profile_id=context.profile_id,
            seed=context.seed,
            preserve_position=command_type != "travel",
        )
        live_events = advance_kernel_runtime(
            context,
            hours_advanced=hours_advanced,
            command_type=command_type,
            command_text=issued,
        )
        generated_events.extend(live_events)
        context.recent_event_log.extend(generated_events)
        context.recent_event_log = context.recent_event_log[-20:]
        if generated_events:
            context.settlement_state["alerts"] = alerts_from_events(generated_events)
        context.settlement_state["current_hour"] = context.world.simulation_snapshot.current_hour
        context.settlement_state["current_day"] = context.world.simulation_snapshot.current_day
        context.settlement_state["season"] = context.world.simulation_snapshot.season
        persist_campaign_state(context)
        dialog_payload = build_dialog_payload(context, narrative) if command_type == "avatar" else {}
        final_payload = campaign_payload(context)
        trace_event(
            "campaign_command_output",
            campaign_id=context.campaign_id,
            command_text=issued,
            command_type=command_type,
            pre_snapshot_hash=pre_hash,
            post_snapshot_hash=snapshot_hash(final_payload),
        )
        return {
            "campaign_id": context.campaign_id,
            "narrative": narrative,
            "command_type": command_type,
            "hours_advanced": hours_advanced,
            "generated_events": generated_events,
            "campaign": final_payload,
            **dialog_payload,
        }

    def snapshot(self, campaign_id: str, narrative: str = "") -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        return {
            "campaign_id": context.campaign_id,
            "adapter_id": context.adapter_id,
            "profile_id": context.profile_id,
            "narrative": narrative,
            "campaign": campaign_payload(context),
        }

    def _resolve_assigned_stats(
        self,
        state: CreationState,
        chosen_class: str,
        assigned_stats: Optional[dict[str, int]],
    ) -> tuple[dict[str, int], str]:
        if not assigned_stats:
            return assign_stats_to_class(state.current_roll, chosen_class), "recommended_roll"
        normalized = {}
        for ability in ABILITY_ORDER:
            if ability not in assigned_stats:
                raise ValueError(f"Missing assigned stat: {ability}")
            value = int(assigned_stats[ability])
            if value < 3 or value > 20:
                raise ValueError(f"Invalid stat value for {ability}: {value}")
            normalized[ability] = value
        if sorted(normalized.values()) == sorted(int(value) for value in state.current_roll):
            return normalized, "rolled_assignment"
        return normalized, "custom_override"


__all__ = ["CampaignRuntime"]
