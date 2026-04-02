from __future__ import annotations

from typing import Any

from engine.kernel import (
    GameState,
    JobRecord,
    apply_morale_cascade,
    assign_labor,
    colony_pressure_from_settlement,
    complete_job,
    compute_power_network,
    decay_needs,
    job_records_from_settlement,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
    production_ledger_from_settlement,
    reaction_defs_from_settlement,
    syndrome_registry_from_actors,
    tick_job,
    worksite_records_from_settlement,
)

from .runtime_common import active_site_id
from .runtime_macro_society import default_stores
from .runtime_systems import load_systems


def job_and_farm_events(context, runtime: dict[str, Any], seed: int) -> list[dict[str, Any]]:
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
            apply_job_outputs(context, job, outputs)
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
        context.settlement_state.setdefault("needs", {})["food"] = max(0, int(context.settlement_state["needs"].get("food", 0)) - 1)
        events.append({"event_type": "farm_harvest", "summary": f"{crop.title()} harvest completed.", "plot_id": plot.get("id")})
    return events


def apply_job_outputs(context, job: JobRecord, outputs: list[dict[str, Any]]) -> None:
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


def refresh_runtime_views(context, runtime: dict[str, Any]) -> None:
    runtime["colony_pressure"] = colony_pressure_from_settlement(context.settlement_state)
    runtime["production_ledger"] = production_ledger_from_settlement(context.settlement_state)
    runtime["path_authority"] = path_authority_from_world(context.world, context.region_snapshot)
    runtime["local_map_state"] = local_map_state_from_region(context.region_snapshot)
    runtime["military"] = military_state_from_settlement(context.settlement_state)
    runtime["systems"]["power_network"] = compute_power_network(context.settlement_state)
    runtime["systems"]["syndrome_registry"] = syndrome_registry_from_actors(list(runtime["actors"].values()))
    project_runtime_to_settlement(context, runtime)
    game_state: GameState = runtime["game_state"]
    game_state.actors = dict(runtime["actors"])
    game_state.current_area_id = context.region_snapshot.region_id
    game_state.loaded_area_ids = [context.region_snapshot.region_id]
    game_state.raw_payload["active_site_id"] = active_site_id(context)
    runtime["world_state"].active_region_id = context.region_snapshot.region_id


def project_runtime_to_settlement(context, runtime: dict[str, Any]) -> None:
    context.settlement_state["jobs"] = [job.to_dict() for job in runtime["jobs"] if "construction" not in set(job.tags)]
    context.settlement_state["construction_queue"] = [job.to_dict() for job in runtime["jobs"] if "construction" in set(job.tags)]
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


def merge_projection_changes_from_settlement(context, runtime: dict[str, Any]) -> None:
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


def rebase_projection_slices(context, runtime: dict[str, Any], *, force: bool = False) -> None:
    if not force and runtime.get("worksites"):
        return
    runtime["jobs"] = job_records_from_settlement(context.settlement_state)
    runtime["reactions"] = reaction_defs_from_settlement(context.settlement_state)
    runtime["worksites"] = worksite_records_from_settlement(context.settlement_state)
    runtime["stores"] = default_stores(context)
    runtime["systems"] = load_systems(None, context)
    runtime["path_authority"] = path_authority_from_world(context.world, context.region_snapshot)
    runtime["local_map_state"] = local_map_state_from_region(context.region_snapshot)
    runtime["military"] = military_state_from_settlement(context.settlement_state)


__all__ = [
    "apply_job_outputs",
    "job_and_farm_events",
    "merge_projection_changes_from_settlement",
    "project_runtime_to_settlement",
    "rebase_projection_slices",
    "refresh_runtime_views",
]
