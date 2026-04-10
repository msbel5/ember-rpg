"""Campaign-first runtime built on top of the world simulation kernel."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Optional

from engine.api.campaign.debug_trace import snapshot_hash, trace_event
from engine.api.campaign.dialog import build_dialog_payload
from engine.api.context_factory import create_player_state
from engine.api.save import SaveSystem
from engine.kernel.creation import ABILITY_ORDER, CreationState, assign_stats_to_class
from engine.kernel import GameState
from engine.worldgen import WorldSeed, initialize_simulation, load_world_snapshot, realize_region

from .context import CampaignContext, CampaignCreationContext
from .live_kernel import ensure_kernel_runtime
from .persistence import campaign_payload, persist_campaign_state
from .quest_bridge import sync_quest_state
from .quest_state import restore_quest_state, snapshot_quest_state
from .runtime_commands import run_command as _run_command
from .runtime_transport import (
    build_transport_payload,
    build_tick_state,
    build_world_ready,
    resolve_runtime_mode,
    sync_tick_loop_mode,
    try_start_tick_loop,
    try_stop_tick_loop,
)
from .state_sync import sync_context_clock
from .controls import merge_settlement_controls
from .region_projection import apply_region_to_context
from .settlement import build_character_sheet, build_settlement_state
from .world import (
    build_world,
    choose_starting_settlement,
    derive_creation_world_seed,
    region_payload,
)


class CampaignRuntime:
    """Owns campaign-first lifecycle, command dispatch, and save/load."""

    def __init__(self):
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
        init_state = create_player_state(
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
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            recent_event_log=[{"event_type": "campaign_start", "summary": opening}],
            player=init_state.player,
            dm_context=init_state.dm_context,
            body_tracker=init_state.body_tracker,
            location_stock=init_state.location_stock,
            ap_tracker=init_state.ap_tracker,
            caravan_manager=init_state.caravan_manager,
            game_time=init_state.game_time,
            spatial_index=init_state.spatial_index,
            viewport=init_state.viewport,
            quest_tracker=init_state.quest_tracker,
            history_seed=init_state.history_seed,
            name_gen=init_state.name_gen,
        )
        apply_region_to_context(
            context=context,
            world=world,
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            campaign_id=campaign_id,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=chosen_seed,
        )
        sync_context_clock(context)
        ensure_kernel_runtime(context)
        sync_quest_state(context)
        sync_tick_loop_mode(context)
        self._campaigns[campaign_id] = context
        persist_campaign_state(context)
        try_start_tick_loop(self, campaign_id)
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
        state = CreationState(
            player_name=player_name,
            adapter_id=adapter_id,
            profile_id=profile_id,
            location=location,
            rng_seed=chosen_seed,
        )
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
            context.dm_context.location = location
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
        try_stop_tick_loop(campaign_id)
        self._campaigns.pop(campaign_id, None)

    def get_current_region(self, campaign_id: str) -> dict[str, Any]:
        return region_payload(self.get_campaign(campaign_id))

    def get_current_settlement(self, campaign_id: str) -> dict[str, Any]:
        return copy.deepcopy(self.get_campaign(campaign_id).settlement_state)

    def build_character_sheet(self, campaign_id: str) -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        return build_character_sheet(context, context.settlement_state)

    def save_campaign(
        self,
        campaign_id: str,
        slot_name: Optional[str] = None,
        player_id: Optional[str] = None,
    ) -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        persist_campaign_state(context)
        chosen_player = (player_id or context.player.name or "player").strip() or "player"
        chosen_slot = slot_name.strip() if slot_name else f"{campaign_id[:8]}_{context.adapter_id}"
        hashed_snapshot = snapshot_hash(campaign_payload(context))
        self.save_system.save_game(context, chosen_slot, player_name=chosen_player)
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
        saves = self.save_system.list_saves(player_name=context.player.name)
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
        context = self.save_system.load_game(save_id, strict=True)
        if context is None:
            raise FileNotFoundError(save_id)
        meta = dict(context.campaign_state.get("campaign") or {})
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
            or build_settlement_state(world, region_snapshot, str(meta.get("adapter_id", "fantasy_ember")), context.player.name)
        )
        context.campaign_id = str(meta.get("campaign_id", context.campaign_id or uuid.uuid4()))
        context.adapter_id = str(meta.get("adapter_id", "fantasy_ember"))
        context.profile_id = str(meta.get("profile_id", world.profile_id))
        context.seed = int(meta.get("seed", world.seed))
        context.world = world
        context.region_snapshot = region_snapshot
        context.settlement_state = settlement_state
        context.recent_event_log = list(meta.get("recent_event_log") or [])
        refreshed_settlement_state = build_settlement_state(world, region_snapshot, context.adapter_id, context.player.name)
        context.settlement_state = merge_settlement_controls(refreshed_settlement_state, settlement_state)
        self._campaigns[context.campaign_id] = context
        preserved_quest_state = snapshot_quest_state(context)
        apply_region_to_context(
            context=context,
            world=world,
            region_snapshot=region_snapshot,
            settlement_state=context.settlement_state,
            campaign_id=context.campaign_id,
            adapter_id=context.adapter_id,
            profile_id=context.profile_id,
            seed=context.seed,
            preserve_position=True,
        )
        restore_quest_state(context, preserved_quest_state, preserve_offers=True)
        sync_context_clock(context)
        ensure_kernel_runtime(context, rebuild_projection=True)
        sync_quest_state(context)
        sync_tick_loop_mode(context)
        try_start_tick_loop(self, context.campaign_id)
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
        result = _run_command(context, input_text, shortcut=shortcut, args=args)
        sync_tick_loop_mode(context)
        result["transport"] = build_transport_payload(context)
        result["runtime_mode"] = resolve_runtime_mode(
            context,
            dialog_payload=build_dialog_payload(context, str(result.get("narrative", ""))),
            campaign_payload=result.get("campaign") if isinstance(result.get("campaign"), dict) else None,
        )
        result["tick_state"] = build_tick_state(context)
        if isinstance(result.get("campaign"), dict):
            result["world_ready"] = build_world_ready(result["campaign"])
        return result

    def snapshot(self, campaign_id: str, narrative: str = "") -> dict[str, Any]:
        context = self.get_campaign(campaign_id)
        dialog_payload = build_dialog_payload(context, narrative)
        sync_tick_loop_mode(context, dialog_payload=dialog_payload)
        payload = campaign_payload(context)
        return {
            "campaign_id": context.campaign_id,
            "adapter_id": context.adapter_id,
            "profile_id": context.profile_id,
            "narrative": narrative,
            "transport": build_transport_payload(context),
            "runtime_mode": resolve_runtime_mode(context, dialog_payload=dialog_payload, campaign_payload=payload),
            "tick_state": build_tick_state(context),
            "world_ready": build_world_ready(payload),
            "campaign": payload,
            **dialog_payload,
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
