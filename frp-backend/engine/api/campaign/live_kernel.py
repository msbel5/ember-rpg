from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.api.campaign_kernel import (
    build_canonical_actor_records,
    build_canonical_game_state,
    build_canonical_world_state,
)
from engine.kernel import (
    ActorRecord,
    GameState,
    JobRecord,
    MilitaryState,
    PathAuthorityState,
    ProductionLedger,
    ReactionDef,
    WorksiteRecord,
    WorldState,
    colony_pressure_from_settlement,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
    production_ledger_from_settlement,
    spread_contagion,
    sync_body_state_to_tracker,
)
from engine.world.body_parts import BodyPartTracker

from .runtime_common import active_site_id, saved_list_or, saved_or, stable_seed
from .runtime_effects import effect_events
from .runtime_macro_society import load_stores, macro_society_events
from .runtime_settlement import (
    job_and_farm_events,
    merge_projection_changes_from_settlement,
    rebase_projection_slices,
    refresh_runtime_views,
)
from .runtime_systems import load_systems, systems_events

if TYPE_CHECKING:
    from .context import CampaignContext


def ensure_kernel_runtime(context: "CampaignContext", *, rebuild_projection: bool = False) -> dict[str, Any]:
    if context.kernel_runtime and not rebuild_projection:
        _sync_runtime_from_session(context, context.kernel_runtime)
        return context.kernel_runtime
    meta = dict(context.session.campaign_state.get("campaign") or {})
    runtime = {
        "world_state": saved_or(
            meta.get("world_state"),
            WorldState,
            lambda: WorldState.from_dict(build_canonical_world_state(context.world)),
        ),
        "game_state": saved_or(
            meta.get("game_state"),
            GameState,
            lambda: build_canonical_game_state(
                context.session,
                campaign_id=context.campaign_id,
                seed=context.seed,
                active_region_id=context.region_snapshot.region_id,
                active_site_id=active_site_id(context),
            ),
        ),
        "actors": _load_actors(meta.get("actors"), context),
        "jobs": saved_list_or(meta.get("jobs"), JobRecord, lambda: []),
        "reactions": saved_list_or(meta.get("reactions"), ReactionDef, lambda: []),
        "worksites": saved_list_or(meta.get("worksites"), WorksiteRecord, lambda: []),
        "colony_pressure": saved_or(
            meta.get("colony_pressure"),
            type(colony_pressure_from_settlement(context.settlement_state)),
            lambda: colony_pressure_from_settlement(context.settlement_state),
        ),
        "production_ledger": saved_or(
            meta.get("production_ledger"),
            ProductionLedger,
            lambda: production_ledger_from_settlement(context.settlement_state),
        ),
        "path_authority": saved_or(
            meta.get("path_authority"),
            PathAuthorityState,
            lambda: path_authority_from_world(context.world, context.region_snapshot),
        ),
        "local_map_state": saved_or(
            meta.get("local_map_state"),
            type(local_map_state_from_region(context.region_snapshot)),
            lambda: local_map_state_from_region(context.region_snapshot),
        ),
        "military": saved_or(
            meta.get("military"),
            MilitaryState,
            lambda: military_state_from_settlement(context.settlement_state),
        ),
        "systems": load_systems(meta.get("systems"), context),
        "stores": load_stores(meta.get("stores"), context),
    }
    context.kernel_runtime = runtime
    rebase_projection_slices(context, runtime, force=True)
    _sync_runtime_from_session(context, runtime)
    return runtime


def serialize_kernel_runtime(context: "CampaignContext") -> dict[str, Any]:
    runtime = ensure_kernel_runtime(context)
    return {
        "world_state": runtime["world_state"].to_dict(),
        "game_state": runtime["game_state"].to_dict(),
        "actors": [actor.to_dict() for actor in runtime["actors"].values()],
        "jobs": [job.to_dict() for job in runtime["jobs"]],
        "reactions": [reaction.to_dict() for reaction in runtime["reactions"]],
        "worksites": [worksite.to_dict() for worksite in runtime["worksites"]],
        "colony_pressure": runtime["colony_pressure"].to_dict(),
        "production_ledger": runtime["production_ledger"].to_dict(),
        "path_authority": runtime["path_authority"].to_dict(),
        "local_map_state": runtime["local_map_state"].to_dict(),
        "military": runtime["military"].to_dict(),
        "systems": {
            "syndrome_registry": [item.to_dict() for item in runtime["systems"]["syndrome_registry"]],
            "power_network": runtime["systems"]["power_network"].to_dict(),
            "traps": [item.to_dict() for item in runtime["systems"]["traps"]],
            "fluid_state": runtime["systems"]["fluid_state"].to_dict(),
            "temperature_state": runtime["systems"]["temperature_state"].to_dict(),
            "strange_mood_incident": runtime["systems"]["strange_mood_incident"].to_dict()
            if runtime["systems"]["strange_mood_incident"] is not None
            else None,
        },
        "stores": [store.to_dict() for store in runtime["stores"]],
    }


def advance_kernel_runtime(
    context: "CampaignContext",
    *,
    hours_advanced: int,
    command_type: str,
    command_text: str,
) -> list[dict[str, Any]]:
    runtime = ensure_kernel_runtime(context, rebuild_projection=command_type == "travel")
    merge_projection_changes_from_settlement(context, runtime)
    _sync_runtime_from_session(context, runtime)
    game_state: GameState = runtime["game_state"]
    actors = list(runtime["actors"].values())
    step_count = max(0, int(hours_advanced))
    seed = stable_seed(
        context.seed,
        context.campaign_id,
        command_type,
        command_text,
        context.world.simulation_snapshot.current_hour,
    )
    events: list[dict[str, Any]] = []
    if step_count > 0:
        game_state.world_time.advance(step_count * max(1, int(game_state.world_time.ticks_per_hour)))
    for step in range(step_count):
        current_tick = int(game_state.world_time.game_tick) + step
        for actor in actors:
            events.extend(effect_events(actor, current_tick))
        infections = spread_contagion(actors, {})
        events.extend(
            {
                "event_type": "syndrome_spread",
                "summary": f"{source_id} infected {target_id}.",
                "source_id": source_id,
                "target_id": target_id,
            }
            for source_id, target_id in infections
        )
        events.extend(_medical_tick_events(actors, current_tick))
        events.extend(job_and_farm_events(context, runtime, seed + step))
        events.extend(macro_society_events(context, runtime))
        events.extend(systems_events(context, runtime, seed + step))
    # ── Progression: check for level-up after all ticks ──────────
    player = runtime["actors"].get("player")
    if player is not None:
        events.extend(_check_level_up(player))
    refresh_runtime_views(context, runtime)
    _sync_runtime_to_session(context, runtime)
    return events


def _check_level_up(player: ActorRecord) -> list[dict[str, Any]]:
    """Advance the shared progression adapter for an ActorRecord.

    Campaign runtime still uses a shared XP table from progression.json
    instead of per-class AD&D tables. This helper formalizes that as a
    narrow adapter over kernel/progression.py so level-up behavior stays
    data-driven and testable without reviving legacy progression code.
    """
    from engine.kernel.progression import can_level_up, execute_level_up

    events: list[dict[str, Any]] = []
    progression_state, class_id, class_def = _progression_adapter(player)
    if progression_state is None or class_def is None:
        return events

    end_mod = (int(player.stats.get("END", 10)) - 10) // 2
    hit_die_roll = _deterministic_hit_die_roll(player, class_id)

    while can_level_up(progression_state, {class_id: class_def}):
        result = execute_level_up(
            progression_state,
            class_id,
            class_def,
            hit_die_roll=hit_die_roll,
            end_modifier=end_mod,
        )
        _apply_progression_state(player, progression_state, result.hp_gained)
        events.append({
            "event_type": "level_up",
            "summary": (
                f"{player.identity.display_name} reached level {progression_state.level}! "
                f"(+{result.hp_gained} HP, max HP now {int(player.stats.get('max_hp', 1))})"
            ),
            "actor_id": player.identity.actor_id,
            "new_level": progression_state.level,
            "hp_gained": result.hp_gained,
            "new_max_hp": int(player.stats.get("max_hp", 1)),
        })

    return events


def _progression_adapter(player: ActorRecord):
    from engine.data.classes import get_class
    from engine.data.runtime import get_xp_thresholds
    from engine.kernel.progression import ClassDef, ProgressionState

    class_id = str(player.raw_payload.get("class_name", "warrior")).lower()
    thresholds = get_xp_thresholds()
    class_data = get_class(class_id)
    if not thresholds:
        return None, None, None

    progression_state = ProgressionState(
        actor_id=player.identity.actor_id,
        xp=int(player.raw_payload.get("xp", 0)),
        level=int(player.raw_payload.get("level", 1)),
        classes=[class_id],
        class_levels={class_id: int(player.raw_payload.get("level", 1))},
        bab=int(player.raw_payload.get("bab", 0)),
        saves=dict(player.raw_payload.get("saves", {})),
    )
    class_def = ClassDef(
        class_id=class_id,
        label=str(class_data.get("name", class_id.title())),
        hit_die=int(class_data.get("hit_die_size", player.raw_payload.get("hit_die_size", 8) or 8)),
        bab_rate=_adapter_bab_rate(player, class_data),
        good_saves=[],
        proficiency_rate=4,
        skill_points_per_level=int(class_data.get("skill_pick_count", 0) or 0),
        spell_type="",
        hp_after_cap=_deterministic_hit_die_roll(player, class_id),
        hit_die_cap_level=len(thresholds),
        xp_table=list(thresholds),
    )
    return progression_state, class_id, class_def


def _adapter_bab_rate(player: ActorRecord, class_data: dict[str, Any]) -> str:
    raw_rate = player.raw_payload.get("bab_rate")
    if isinstance(raw_rate, str):
        return raw_rate
    if raw_rate is not None:
        rate = float(raw_rate)
        if rate >= 1.0:
            return "full"
        if rate >= 0.75:
            return "three_quarter"
        return "half"
    hit_die = int(class_data.get("hit_die_size", player.raw_payload.get("hit_die_size", 8) or 8))
    if hit_die >= 10:
        return "full"
    if hit_die >= 8:
        return "three_quarter"
    return "half"


def _deterministic_hit_die_roll(player: ActorRecord, class_id: str) -> int:
    from engine.data.runtime import get_hp_per_level

    hp_per_level = get_hp_per_level()
    return max(
        1,
        int(
            hp_per_level.get(
                class_id,
                player.raw_payload.get("hit_die_size", 8) or 8,
            )
        ),
    )


def _apply_progression_state(player: ActorRecord, progression_state: Any, hp_gained: int) -> None:
    new_max_hp = int(player.stats.get("max_hp", 1)) + int(hp_gained)
    player.stats["max_hp"] = new_max_hp
    player.stats["hp"] = new_max_hp
    player.raw_payload["level"] = int(progression_state.level)
    player.raw_payload["xp"] = int(progression_state.xp)
    player.raw_payload["bab"] = int(progression_state.bab)
    player.raw_payload["saves"] = dict(progression_state.saves)
    player.raw_payload["progression"] = progression_state.to_dict()


def _load_actors(saved_payload: Any, context: "CampaignContext") -> dict[str, ActorRecord]:
    if isinstance(saved_payload, list):
        return {actor.identity.actor_id: actor for actor in [ActorRecord.from_dict(dict(item)) for item in saved_payload]}
    return {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context.session,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }


def _sync_runtime_from_session(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    fresh_actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context.session,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }
    merged: dict[str, ActorRecord] = {}
    for actor_id, fresh_actor in fresh_actors.items():
        existing = runtime["actors"].get(actor_id)
        if existing is None:
            merged[actor_id] = fresh_actor
            continue
        _merge_actor(existing, fresh_actor)
        merged[actor_id] = existing
    runtime["actors"] = merged
    runtime["game_state"].actors = dict(merged)
    runtime["game_state"].party = ["player"] if "player" in merged else []
    runtime["game_state"].inactive_npcs = [actor_id for actor_id in merged if actor_id not in runtime["game_state"].party]


def _sync_runtime_to_session(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    actors = runtime["actors"]
    player = actors.get("player")
    if player is not None:
        context.session.player.hp = int(player.stats.get("hp", context.session.player.hp))
        context.session.player.max_hp = int(player.stats.get("max_hp", context.session.player.max_hp))
        context.session.player.conditions = player.condition_names
        # Sync XP and level from kernel ActorRecord to session player.
        # ActorRecord.level is a read-only property backed by raw_payload,
        # so we write to raw_payload directly.  xp has a proper setter.
        context.session.player.xp = int(player.raw_payload.get("xp", 0))
        context.session.player.raw_payload["level"] = int(player.raw_payload.get("level", 1))
        if context.session.body_tracker is None:
            context.session.body_tracker = BodyPartTracker()
        if player.body_state is not None:
            sync_body_state_to_tracker(player.body_state, context.session.body_tracker)
        if context.session.player_entity is not None:
            context.session.player_entity.hp = context.session.player.hp
            context.session.player_entity.max_hp = context.session.player.max_hp
            context.session.player_entity.position = (player.position.x, player.position.y)
    for entity_id, record in context.session.entities.items():
        actor = actors.get(entity_id)
        live_entity = record.get("entity_ref")
        if actor is None or live_entity is None:
            continue
        live_entity.position = (actor.position.x, actor.position.y)
        live_entity.hp = int(actor.stats.get("hp", live_entity.hp))
        live_entity.max_hp = int(actor.stats.get("max_hp", live_entity.max_hp))
        live_entity.alive = bool(actor.alive)
        if actor.body_state is not None:
            live_entity.body = actor.body_state.to_tracker()
            record["body"] = live_entity.body
        record["position"] = [actor.position.x, actor.position.y]
        record["hp"] = live_entity.hp
        record["max_hp"] = live_entity.max_hp
        record["alive"] = live_entity.alive
        record["needs"] = actor.needs.to_dict()
        record["schedule"] = actor.schedule.to_dict()


def _merge_actor(target: ActorRecord, fresh: ActorRecord) -> None:
    target.action_points = fresh.action_points
    target.max_action_points = fresh.max_action_points
    target.turn_resources = dict(fresh.turn_resources)
    target.alive = target.alive and fresh.alive
    for key, value in fresh.stats.items():
        if key in {"hp", "max_hp"} or key not in target.stats:
            target.stats[key] = value
    for key, value in fresh.skills.items():
        target.skills.setdefault(key, value)
    target.inventory = fresh.inventory
    target.equipment = fresh.equipment
    # Preserve progression fields (xp, level) that the kernel owns.
    preserved_xp = target.raw_payload.get("xp")
    preserved_level = target.raw_payload.get("level")
    target.raw_payload.update(fresh.raw_payload)
    if preserved_xp is not None:
        target.raw_payload["xp"] = max(int(preserved_xp), int(target.raw_payload.get("xp", 0)))
    if preserved_level is not None:
        target.raw_payload["level"] = max(int(preserved_level), int(target.raw_payload.get("level", 1)))
    if target.body_state is None:
        target.body_state = fresh.body_state
    elif target.body_state is not None and fresh.body_state is not None:
        for part_id, part in fresh.body_state.parts.items():
            existing_part = target.body_state.parts.get(part_id)
            if existing_part is None:
                target.body_state.parts[part_id] = part
                continue
            existing_part.max_hp = max(existing_part.max_hp, part.max_hp)
            existing_part.current_hp = min(existing_part.current_hp, part.current_hp)
    if target.schedule.owner_id == "" and fresh.schedule.owner_id:
        target.schedule = fresh.schedule


def _medical_tick_events(actors: list, current_tick: int) -> list[dict[str, Any]]:
    """Advance infection and recovery states for all actors."""
    from engine.kernel.medical import InfectionState, RecoveryState, tick_infection, tick_recovery
    events: list[dict[str, Any]] = []
    for actor in actors:
        for infection in actor.raw_payload.get("medical_infections", []):
            if isinstance(infection, InfectionState):
                prev = infection.infection_level
                tick_infection(infection, 1)
                if infection.infection_level > prev:
                    events.append({
                        "event_type": "infection_progress",
                        "summary": f"{actor.identity.display_name}: infection advanced to {infection.infection_level:.0%}.",
                        "actor_id": actor.identity.actor_id,
                    })
        for recovery in actor.raw_payload.get("medical_recoveries", []):
            if isinstance(recovery, RecoveryState):
                healed = tick_recovery(recovery, 1)
                if healed > 0:
                    events.append({
                        "event_type": "medical_recovery",
                        "summary": f"{actor.identity.display_name}: recovered {healed} hp.",
                        "actor_id": actor.identity.actor_id,
                    })
    return events


__all__ = ["advance_kernel_runtime", "ensure_kernel_runtime", "serialize_kernel_runtime", "_check_level_up"]
