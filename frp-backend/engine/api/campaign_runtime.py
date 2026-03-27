"""Campaign-first runtime built on top of the world simulation kernel."""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from engine.api.game_engine import GameEngine
from engine.api.game_session import GameSession
from engine.api.save_system import SaveSystem
from engine.worldgen import load_world_snapshot, realize_region, tick_global
from engine.worldgen.models import RegionSnapshot, WorldBlueprint

from .campaign_commands import (
    handle_travel,
    hours_for_avatar_command,
    maybe_handle_commander_command,
    merge_avatar_narrative,
    resolve_command_text,
)
from .campaign_state import (
    alerts_from_events,
    apply_region_to_session,
    build_settlement_state,
    build_world,
    campaign_payload,
    persist_campaign_state,
    region_payload,
)


@dataclass
class CampaignContext:
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int
    world: WorldBlueprint
    session: GameSession
    region_snapshot: RegionSnapshot
    settlement_state: dict[str, Any]
    recent_event_log: list[dict[str, Any]] = field(default_factory=list)


class CampaignRuntime:
    """Owns campaign-first lifecycle, command dispatch, and save/load."""

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        self.engine = GameEngine(llm=llm)
        self.save_system = SaveSystem()
        self._campaigns: dict[str, CampaignContext] = {}

    def create_campaign(
        self,
        player_name: str,
        player_class: str = "warrior",
        adapter_id: str = "fantasy_ember",
        profile_id: str = "standard",
        seed: Optional[int] = None,
    ) -> CampaignContext:
        chosen_seed = seed if seed is not None else abs(hash((player_name, adapter_id, profile_id))) % (2**31)
        world = build_world(adapter_id=adapter_id, profile_id=profile_id, seed=chosen_seed)
        settlement = world.settlements[0]
        region_snapshot = realize_region(world, settlement.region_id)
        session = self.engine.new_session(
            player_name=player_name,
            player_class=player_class,
            location=settlement.center_name,
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
        self._campaigns[campaign_id] = context
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
        self.save_system.save_game(context.session, chosen_slot, player_name=chosen_player)
        return self.save_system.get_save_metadata(chosen_slot) or {
            "slot_name": chosen_slot,
            "timestamp": "",
            "schema_version": "",
        }

    def list_campaign_saves(self, campaign_id: str) -> list[dict[str, Any]]:
        context = self.get_campaign(campaign_id)
        return self.save_system.list_saves(player_name=context.session.player.name)

    def load_campaign(self, save_id: str) -> CampaignContext:
        session = self.save_system.load_game(save_id, strict=True)
        if session is None:
            raise FileNotFoundError(save_id)
        meta = dict(session.campaign_state.get("campaign_v2") or {})
        if not meta:
            raise ValueError(f"Save {save_id} does not contain campaign_v2 state")
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
        self._campaigns[context.campaign_id] = context
        apply_region_to_session(
            session=session,
            world=world,
            region_snapshot=region_snapshot,
            settlement_state=settlement_state,
            campaign_id=context.campaign_id,
            adapter_id=context.adapter_id,
            profile_id=context.profile_id,
            seed=context.seed,
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
        issued = resolve_command_text(input_text=input_text, shortcut=shortcut, args=dict(args or {}))
        lower = issued.lower()
        if lower.startswith("travel"):
            narrative = handle_travel(context, issued)
            command_type = "travel"
            hours_advanced = 4
        else:
            handled = maybe_handle_commander_command(context, issued)
            if handled is not None:
                narrative, command_type, hours_advanced = handled
            else:
                result = self.engine.process_action(context.session, issued)
                narrative = merge_avatar_narrative(context, result.narrative)
                command_type = "avatar"
                hours_advanced = hours_for_avatar_command(lower)

        tick_result = tick_global(context.world, hours_advanced)
        generated_events = list(tick_result.generated_events)
        context.recent_event_log.extend(generated_events)
        context.recent_event_log = context.recent_event_log[-20:]
        context.settlement_state["alerts"] = alerts_from_events(generated_events)
        context.settlement_state["current_hour"] = context.world.simulation_snapshot.current_hour
        persist_campaign_state(context)
        return {
            "campaign_id": context.campaign_id,
            "narrative": narrative,
            "command_type": command_type,
            "hours_advanced": hours_advanced,
            "generated_events": generated_events,
            "campaign": campaign_payload(context),
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
