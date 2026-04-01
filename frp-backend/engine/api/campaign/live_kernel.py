from __future__ import annotations

import copy
import hashlib
from typing import TYPE_CHECKING, Any

from engine.api.campaign_kernel import (
    build_canonical_actor_records,
    build_canonical_game_state,
    build_canonical_world_state,
)
from engine.kernel import (
    ActorRecord,
    FluidState,
    GameState,
    JobRecord,
    MilitaryState,
    PathAuthorityState,
    PowerNetworkState,
    ProductionLedger,
    ReactionDef,
    StoreDef,
    StoreItem,
    StoreService,
    StrangeMoodIncident,
    SyndromeDef,
    TemperatureState,
    TrapState,
    WorksiteRecord,
    WoundRecord,
    WorldState,
    adjust_store_prices,
    apply_morale_cascade,
    assign_labor,
    check_drowning,
    check_magma_damage,
    check_trap_triggers,
    colony_pressure_from_settlement,
    complete_job,
    compute_power_network,
    decay_needs,
    fluid_state_from_region,
    job_records_from_settlement,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
    power_network_from_settlement,
    production_ledger_from_settlement,
    reaction_defs_from_settlement,
    resolve_trap_damage,
    spread_contagion,
    strange_mood_incident_from_settlement,
    syndrome_registry_from_actors,
    sync_body_state_to_tracker,
    temperature_state_from_region,
    tick_effects,
    tick_fluids,
    tick_job,
    tick_strange_mood,
    tick_syndromes,
    tick_temperature,
    trap_state_from_settlement,
    worksite_records_from_settlement,
)
from engine.world.body_parts import BodyPartTracker

if TYPE_CHECKING:
    from .context import CampaignContext


def ensure_kernel_runtime(context: "CampaignContext", *, rebuild_projection: bool = False) -> dict[str, Any]:
    if context.kernel_runtime and not rebuild_projection:
        _sync_runtime_from_session(context, context.kernel_runtime)
        return context.kernel_runtime
    meta = dict(context.session.campaign_state.get("campaign_v2") or {})
    runtime = {
        "world_state": _saved_or(
            meta.get("kernel_world_state"),
            WorldState,
            lambda: WorldState.from_dict(build_canonical_world_state(context.world)),
        ),
        "game_state": _saved_or(
            meta.get("kernel_game_state"),
            GameState,
            lambda: build_canonical_game_state(
                context.session,
                campaign_id=context.campaign_id,
                seed=context.seed,
                active_region_id=context.region_snapshot.region_id,
                active_site_id=_active_site_id(context),
            ),
        ),
        "actors": _load_actors(meta.get("kernel_actors"), context),
        "jobs": _saved_list_or(meta.get("kernel_jobs"), JobRecord, lambda: job_records_from_settlement(context.settlement_state)),
        "reactions": _saved_list_or(
            meta.get("kernel_reactions"),
            ReactionDef,
            lambda: reaction_defs_from_settlement(context.settlement_state),
        ),
        "worksites": _saved_list_or(
            meta.get("kernel_worksites"),
            WorksiteRecord,
            lambda: worksite_records_from_settlement(context.settlement_state),
        ),
        "colony_pressure": _saved_or(
            meta.get("kernel_colony_pressure"),
            type(colony_pressure_from_settlement(context.settlement_state)),
            lambda: colony_pressure_from_settlement(context.settlement_state),
        ),
        "production_ledger": _saved_or(
            meta.get("kernel_production_ledger"),
            ProductionLedger,
            lambda: production_ledger_from_settlement(context.settlement_state),
        ),
        "path_authority": _saved_or(
            meta.get("kernel_path_authority"),
            PathAuthorityState,
            lambda: path_authority_from_world(context.world, context.region_snapshot),
        ),
        "local_map_state": _saved_or(
            meta.get("kernel_local_map_state"),
            type(local_map_state_from_region(context.region_snapshot)),
            lambda: local_map_state_from_region(context.region_snapshot),
        ),
        "military": _saved_or(
            meta.get("kernel_military"),
            MilitaryState,
            lambda: military_state_from_settlement(context.settlement_state),
        ),
        "systems": _load_systems(meta.get("kernel_systems"), context),
        "stores": _load_stores(meta.get("kernel_stores"), context),
    }
    context.kernel_runtime = runtime
    _rebase_projection_slices(context, runtime, force=True)
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
    _merge_projection_changes_from_settlement(context, runtime)
    _sync_runtime_from_session(context, runtime)
    game_state: GameState = runtime["game_state"]
    actors = list(runtime["actors"].values())
    step_count = max(1, int(hours_advanced))
    seed = _stable_seed(
        context.seed,
        context.campaign_id,
        command_type,
        command_text,
        context.world.simulation_snapshot.current_hour,
    )
    events: list[dict[str, Any]] = []
    game_state.world_time.advance(step_count * max(1, int(game_state.world_time.ticks_per_hour)))
    for step in range(step_count):
        current_tick = int(game_state.world_time.game_tick) + step
        for actor in actors:
            events.extend(_effect_events(actor, current_tick))
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
        events.extend(_job_and_farm_events(context, runtime, seed + step))
        events.extend(_macro_society_events(context, runtime))
        events.extend(_systems_events(context, runtime, seed + step))
    _refresh_runtime_views(context, runtime)
    _sync_runtime_to_session(context, runtime)
    return events


def _effect_events(actor: ActorRecord, current_tick: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for effect_event in tick_effects(actor, current_tick):
        events.append(
            {"event_type": effect_event["type"], "summary": f"{actor.identity.display_name} {effect_event['type']}."}
        )
    for syndrome_event in tick_syndromes(actor):
        events.append(
            {"event_type": "syndrome_tick", "summary": f"{actor.identity.display_name} suffered {syndrome_event}."}
        )
    if actor.body_state is not None and not actor.body_state.is_viable():
        actor.alive = False
        actor.stats["hp"] = 0
    return events


def _job_and_farm_events(context: "CampaignContext", runtime: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    actor_map = runtime["actors"]
    candidates = list(actor_map.values())
    for actor in candidates:
        decay_needs(actor, 1)
    runtime["colony_pressure"] = colony_pressure_from_settlement(context.settlement_state)
    apply_morale_cascade(candidates, runtime["colony_pressure"].unrest)
    events: list[dict[str, Any]] = []
    reaction_lookup = {reaction.reaction_id: reaction for reaction in runtime["reactions"]}
    for job in runtime["jobs"]:
        if job.status == "idle":
            job.status = "queued"
        if job.status == "queued":
            assignee_id = assign_labor(job, candidates, runtime["worksites"])
            if assignee_id is not None:
                job.assignee_id = assignee_id
                job.status = "assigned"
        if job.status == "assigned":
            job.transition_to("active")
        if job.status != "active" or not job.assignee_id:
            continue
        assignee = actor_map.get(job.assignee_id)
        if assignee is None:
            continue
        speed = float(assignee.needs.modifiers.get("work_speed_mult", 1.0))
        if tick_job(job, assignee, work_speed_mult=max(1.0, speed)):
            reaction = reaction_lookup.get(f"{job.kind}_reaction")
            if reaction is None:
                reaction = next((item for item in runtime["reactions"] if item.worksite_kind == job.kind), None)
            if reaction is None:
                continue
            _, _, outputs = complete_job(job, assignee, reaction, rng_value=((seed % 1000) / 1000.0))
            _apply_job_outputs(context, job, outputs)
            events.append({"event_type": "job_completed", "summary": f"{job.kind} completed.", "job_id": job.job_id})
    for plot in context.settlement_state.setdefault("farm_plots", []):
        if not bool(plot.get("active", False)):
            continue
        growth_target = max(1, int(plot.get("growth_target", 100)))
        plot["growth_ticks"] = int(plot.get("growth_ticks", 0)) + 5
        if int(plot["growth_ticks"]) < growth_target:
            continue
        plot["growth_ticks"] = 0
        plot["yield"] = int(plot.get("yield", 0)) + 1
        crop = str(plot.get("crop", "food"))
        seed_stock = context.settlement_state.setdefault("seed_stock", {})
        seed_stock[crop] = int(seed_stock.get(crop, 0)) + 1
        economy = context.settlement_state.setdefault("economy", {})
        resources = economy.setdefault("resources", {})
        resources["food"] = int(resources.get("food", 0)) + 1
        context.settlement_state.setdefault("needs", {})["food"] = max(
            0,
            int(context.settlement_state["needs"].get("food", 0)) - 1,
        )
        events.append({"event_type": "farm_harvest", "summary": f"{crop.title()} harvest completed.", "plot_id": plot.get("id")})
    return events


def _apply_job_outputs(context: "CampaignContext", job: JobRecord, outputs: list[dict[str, Any]]) -> None:
    economy = context.settlement_state.setdefault("economy", {})
    resources = economy.setdefault("resources", {})
    needs = context.settlement_state.setdefault("needs", {})
    available_materials = context.settlement_state.setdefault("available_materials", [])
    for output in outputs:
        material_id = str(output.get("material_id", "generic"))
        item_def_id = str(output.get("item_def_id", material_id))
        quantity = int(output.get("quantity", 1))
        resources[material_id] = int(resources.get(material_id, 0)) + quantity
        resources[item_def_id] = int(resources.get(item_def_id, 0)) + quantity
        available_materials.append(material_id)
    if job.kind in {"forge", "construction"}:
        needs["materials"] = max(0, int(needs.get("materials", 0)) - 1)
    if job.kind in {"cook", "brew", "farm", "harvest"}:
        needs["food"] = max(0, int(needs.get("food", 0)) - 1)


def _macro_society_events(context: "CampaignContext", runtime: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    ledger: ProductionLedger = production_ledger_from_settlement(context.settlement_state)
    runtime["production_ledger"] = ledger
    pressure = colony_pressure_from_settlement(context.settlement_state)
    runtime["colony_pressure"] = pressure
    for store in runtime["stores"]:
        adjust_store_prices(store, ledger)
        if ledger.shortages:
            for item in store.items:
                item.price_multiplier = round(float(item.price_multiplier) * (1.0 + (0.05 * len(ledger.shortages))), 4)
        elif ledger.surpluses:
            market_discount = max(0.85, 1.0 - (0.03 * len(ledger.surpluses)))
            for item in store.items:
                item.price_multiplier = round(float(item.price_multiplier) * market_discount, 4)
        for item in store.items:
            context.settlement_state.setdefault("economy", {}).setdefault("prices", {})[item.item_def_id] = item.price_multiplier
    current_hour = int(context.world.simulation_snapshot.current_hour)
    caravan_events = context.session.caravan_manager.tick(current_hour)
    world_state: WorldState = runtime["world_state"]
    world_state.active_caravans = context.session.caravan_manager.get_active_caravans()
    for event in caravan_events:
        if event.get("type") != "arrival":
            continue
        goods = dict(event.get("goods_delivered", {}))
        for store in runtime["stores"]:
            _restock_store(store, goods)
        resources = context.settlement_state.setdefault("economy", {}).setdefault("resources", {})
        for item_id, quantity in goods.items():
            resources[item_id] = int(resources.get(item_id, 0)) + int(quantity)
        events.append({"event_type": "caravan_arrival", "summary": f"A caravan arrived with {', '.join(goods.keys())}."})
    region = world_state.regions.get(context.region_snapshot.region_id)
    if region is not None:
        region.economy.setdefault("prices", {}).update(context.settlement_state.setdefault("economy", {}).get("prices", {}))
    for faction_id, faction in world_state.factions.items():
        for other_id in world_state.factions:
            if faction_id == other_id:
                continue
            faction.relations.setdefault(other_id, 0)
            delta = 1 if not ledger.shortages else -len(ledger.shortages)
            faction.relations[other_id] = max(-100, min(100, int(faction.relations[other_id]) + delta))
    if "migration_candidate" in pressure.pressure_tags:
        wave_id = f"{context.region_snapshot.region_id}:{context.world.simulation_snapshot.current_day}"
        if not any(wave.get("wave_id") == wave_id for wave in world_state.migration_waves):
            population_delta = max(1, int(context.settlement_state.get("population", 1)) // 10)
            world_state.migration_waves.append(
                {
                    "wave_id": wave_id,
                    "region_id": context.region_snapshot.region_id,
                    "settlement_id": _active_site_id(context),
                    "population_delta": population_delta,
                    "reason": "prosperity",
                }
            )
            context.settlement_state["population"] = int(context.settlement_state.get("population", 0)) + population_delta
            settlement = world_state.settlements.get(_active_site_id(context))
            if settlement is not None:
                settlement.population += population_delta
            events.append({"event_type": "migration_wave", "summary": "New settlers arrived at the frontier."})
    if pressure.unrest >= 60 and region is not None and region.controller_faction_id:
        change_id = f"{context.region_snapshot.region_id}:{context.world.simulation_snapshot.current_day}:unrest"
        if not any(change.get("change_id") == change_id for change in world_state.ownership_changes):
            world_state.ownership_changes.append(
                {
                    "change_id": change_id,
                    "region_id": context.region_snapshot.region_id,
                    "faction_id": region.controller_faction_id,
                    "reason": "unrest",
                }
            )
    return events


def _systems_events(context: "CampaignContext", runtime: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    systems = runtime["systems"]
    actors = list(runtime["actors"].values())
    terrain = copy.deepcopy(context.region_snapshot.typed_tiles)
    if not systems["traps"]:
        systems["traps"] = trap_state_from_settlement(context.settlement_state)
    systems["power_network"] = compute_power_network(context.settlement_state)
    systems["fluid_state"] = tick_fluids(systems["fluid_state"], terrain)
    events: list[dict[str, Any]] = []
    for actor in actors:
        if check_drowning(actor, systems["fluid_state"]):
            events.append({"event_type": "drowning", "summary": f"{actor.identity.display_name} drowned."})
        magma_wound = check_magma_damage(actor, systems["fluid_state"])
        if magma_wound is not None:
            events.append({"event_type": "magma", "summary": f"{actor.identity.display_name} was burned by magma."})
    for temp_event in tick_temperature(systems["temperature_state"], actors):
        actor = runtime["actors"].get(temp_event.get("actor_id"))
        if actor is not None and actor.body_state is not None and temp_event["type"] in {"frostbite", "heat"}:
            actor.body_state.apply_wound(
                WoundRecord.from_dict(
                    {
                        "wound_id": f"{temp_event['type']}:{temp_event['actor_id']}:{len(actor.body_state.wounds)}",
                        "body_part_id": "torso",
                        "damage_type": "cold" if temp_event["type"] == "frostbite" else "fire",
                        "damage_amount": 6,
                        "bleeding": 0,
                        "pain": 6,
                        "open_wound": temp_event["type"] == "heat",
                        "untreated": True,
                    }
                )
            )
        events.append({"event_type": temp_event["type"], "summary": str(temp_event)})
    trap_positions = {str(key): tuple(value) for key, value in dict(context.settlement_state.get("trap_positions", {})).items()}
    unit_positions = {
        actor.identity.actor_id: {"position": [actor.position.x, actor.position.y], "tags": list(actor.identity.tags)}
        for actor in actors
    }
    for event in check_trap_triggers(systems["traps"], unit_positions, trap_positions):
        target = runtime["actors"].get(event["target_actor_id"])
        trap = next((item for item in systems["traps"] if item.trap_id == event["trap_id"]), None)
        if target is None or trap is None:
            continue
        resolve_trap_damage(trap, target, seed)
        events.append({"event_type": "trap_triggered", "summary": f"{target.identity.display_name} triggered {trap.trap_id}."})
    incident = systems.get("strange_mood_incident")
    if incident is None:
        incident = strange_mood_incident_from_settlement(context.settlement_state, runtime["colony_pressure"])
    if incident is not None:
        context.settlement_state["worksites"] = [worksite.to_dict() for worksite in runtime["worksites"]]
        systems["strange_mood_incident"] = tick_strange_mood(incident, context.settlement_state, actors, seed)
    systems["syndrome_registry"] = syndrome_registry_from_actors(actors)
    return events


def _refresh_runtime_views(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    runtime["colony_pressure"] = colony_pressure_from_settlement(context.settlement_state)
    runtime["production_ledger"] = production_ledger_from_settlement(context.settlement_state)
    runtime["path_authority"] = path_authority_from_world(context.world, context.region_snapshot)
    runtime["local_map_state"] = local_map_state_from_region(context.region_snapshot)
    runtime["military"] = military_state_from_settlement(context.settlement_state)
    runtime["systems"]["power_network"] = compute_power_network(context.settlement_state)
    runtime["systems"]["syndrome_registry"] = syndrome_registry_from_actors(list(runtime["actors"].values()))
    _project_runtime_to_settlement(context, runtime)
    game_state: GameState = runtime["game_state"]
    game_state.actors = dict(runtime["actors"])
    game_state.current_area_id = context.region_snapshot.region_id
    game_state.loaded_area_ids = [context.region_snapshot.region_id]
    game_state.raw_payload["active_site_id"] = _active_site_id(context)
    runtime["world_state"].active_region_id = context.region_snapshot.region_id


def _project_runtime_to_settlement(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    context.settlement_state["jobs"] = [job.to_dict() for job in runtime["jobs"] if "construction" not in set(job.tags)]
    context.settlement_state["construction_queue"] = [
        job.to_dict() for job in runtime["jobs"] if "construction" in set(job.tags)
    ]
    context.settlement_state["worksites"] = [worksite.to_dict() for worksite in runtime["worksites"]]
    actor_map = runtime["actors"]
    for resident in context.settlement_state.get("residents", []):
        actor_id = "player" if resident.get("id") == "player_commander" else str(resident.get("id", ""))
        actor = actor_map.get(actor_id)
        if actor is None:
            continue
        resident["mood"] = actor.needs.mood
        active_job = next((job for job in runtime["jobs"] if job.assignee_id == actor_id and job.status == "active"), None)
        if active_job is not None:
            resident["assignment"] = active_job.kind
    context.settlement_state["current_hour"] = context.world.simulation_snapshot.current_hour
    context.settlement_state["current_day"] = context.world.simulation_snapshot.current_day
    context.settlement_state["season"] = context.world.simulation_snapshot.season


def _sync_runtime_from_session(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    fresh_actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context.session,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=_active_site_id(context),
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
        context.session.player.conditions = [condition.name for condition in player.conditions]
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
    target.alive = target.alive and fresh.alive
    for key, value in fresh.stats.items():
        if key in {"hp", "max_hp"} or key not in target.stats:
            target.stats[key] = value
    for key, value in fresh.skills.items():
        target.skills.setdefault(key, value)
    target.inventory = fresh.inventory
    target.equipment = fresh.equipment
    target.raw_payload.update(fresh.raw_payload)
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


def _merge_projection_changes_from_settlement(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    fresh_jobs = {job.job_id: job for job in job_records_from_settlement(context.settlement_state)}
    current_jobs = {job.job_id: job for job in runtime["jobs"]}
    merged_jobs: list[JobRecord] = []
    for job_id, fresh_job in fresh_jobs.items():
        current = current_jobs.get(job_id)
        if current is None:
            merged_jobs.append(fresh_job)
            continue
        current.kind = fresh_job.kind
        current.priority = fresh_job.priority
        current.worksite_id = fresh_job.worksite_id
        current.room_id = fresh_job.room_id
        current.skill_id = fresh_job.skill_id
        current.tags = list(fresh_job.tags)
        if current.status in {"completed", "cancelled"}:
            merged_jobs.append(current)
        else:
            if fresh_job.assignee_id:
                current.assignee_id = fresh_job.assignee_id
            merged_jobs.append(current)
    runtime["jobs"] = merged_jobs
    runtime["reactions"] = reaction_defs_from_settlement(context.settlement_state)
    runtime["worksites"] = worksite_records_from_settlement(context.settlement_state)
    if str(context.settlement_state.get("defense_posture", "normal")) == "fortified" and not runtime["systems"]["traps"]:
        runtime["systems"]["traps"] = trap_state_from_settlement(context.settlement_state)


def _rebase_projection_slices(context: "CampaignContext", runtime: dict[str, Any], *, force: bool = False) -> None:
    if not force and runtime.get("worksites"):
        return
    runtime["jobs"] = job_records_from_settlement(context.settlement_state)
    runtime["reactions"] = reaction_defs_from_settlement(context.settlement_state)
    runtime["worksites"] = worksite_records_from_settlement(context.settlement_state)
    runtime["stores"] = _default_stores(context)
    runtime["systems"] = _load_systems(None, context)
    runtime["path_authority"] = path_authority_from_world(context.world, context.region_snapshot)
    runtime["local_map_state"] = local_map_state_from_region(context.region_snapshot)
    runtime["military"] = military_state_from_settlement(context.settlement_state)


def _load_actors(saved_payload: Any, context: "CampaignContext") -> dict[str, ActorRecord]:
    if isinstance(saved_payload, list):
        return {actor.identity.actor_id: actor for actor in [ActorRecord.from_dict(dict(item)) for item in saved_payload]}
    return {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context.session,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=_active_site_id(context),
        )
    }


def _load_systems(saved_payload: Any, context: "CampaignContext") -> dict[str, Any]:
    if isinstance(saved_payload, dict):
        return {
            "syndrome_registry": [
                item if isinstance(item, SyndromeDef) else SyndromeDef.from_dict(dict(item))
                for item in saved_payload.get("syndrome_registry", [])
            ],
            "power_network": _saved_or(
                saved_payload.get("power_network"),
                PowerNetworkState,
                lambda: power_network_from_settlement(context.settlement_state),
            ),
            "traps": [
                item if isinstance(item, TrapState) else TrapState.from_dict(dict(item))
                for item in saved_payload.get("traps", [])
            ],
            "fluid_state": _saved_or(
                saved_payload.get("fluid_state"),
                FluidState,
                lambda: fluid_state_from_region(context.region_snapshot),
            ),
            "temperature_state": _saved_or(
                saved_payload.get("temperature_state"),
                TemperatureState,
                lambda: temperature_state_from_region(context.region_snapshot),
            ),
            "strange_mood_incident": _saved_or(
                saved_payload.get("strange_mood_incident"),
                StrangeMoodIncident,
                lambda: None,
            ),
        }
    colony_pressure = colony_pressure_from_settlement(context.settlement_state)
    return {
        "syndrome_registry": [],
        "power_network": power_network_from_settlement(context.settlement_state),
        "traps": trap_state_from_settlement(context.settlement_state),
        "fluid_state": fluid_state_from_region(context.region_snapshot),
        "temperature_state": temperature_state_from_region(context.region_snapshot),
        "strange_mood_incident": strange_mood_incident_from_settlement(context.settlement_state, colony_pressure),
    }


def _load_stores(saved_payload: Any, context: "CampaignContext") -> list[StoreDef]:
    if isinstance(saved_payload, list):
        return [item if isinstance(item, StoreDef) else StoreDef.from_dict(dict(item)) for item in saved_payload]
    return _default_stores(context)


def _default_stores(context: "CampaignContext") -> list[StoreDef]:
    resources = dict(context.settlement_state.get("economy", {}).get("resources", {}))
    items = [
        StoreItem(item_def_id=str(item_id), quantity=max(1, int(quantity)), price_multiplier=1.0)
        for item_id, quantity in sorted(resources.items())
        if int(quantity) > 0
    ]
    if not items:
        items = [StoreItem(item_def_id="food", quantity=10), StoreItem(item_def_id="materials", quantity=6)]
    services = [
        StoreService(service_id="rest", service_type="room", label="Room for the night", price=5, room_quality=1.0),
        StoreService(service_id="identify", service_type="identify", label="Identify item", price=10),
    ]
    return [
        StoreDef(
            store_id=f"{_active_site_id(context)}_market",
            label=f"{context.settlement_state.get('name', 'Frontier')} Market",
            store_type="market",
            items=items,
            services=services,
        )
    ]


def _restock_store(store: StoreDef, goods: dict[str, Any]) -> None:
    for item_id, quantity in goods.items():
        existing = next((item for item in store.items if item.item_def_id == item_id), None)
        if existing is None:
            store.items.append(StoreItem(item_def_id=str(item_id), quantity=int(quantity), price_multiplier=1.0))
        else:
            existing.quantity = max(0, int(existing.quantity)) + int(quantity)


def _saved_or(payload: Any, cls: type, fallback):
    if payload is None:
        return fallback()
    if isinstance(payload, cls):
        return payload
    if hasattr(cls, "from_dict"):
        return cls.from_dict(dict(payload))
    return fallback()


def _saved_list_or(payload: Any, cls: type, fallback):
    if not isinstance(payload, list):
        return fallback()
    return [item if isinstance(item, cls) else cls.from_dict(dict(item)) for item in payload]


def _stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _active_site_id(context: "CampaignContext") -> str:
    return str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or context.region_snapshot.region_id
    )


__all__ = [
    "advance_kernel_runtime",
    "ensure_kernel_runtime",
    "serialize_kernel_runtime",
]
