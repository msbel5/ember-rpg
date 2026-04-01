"""Control-state merging helpers for campaign settlement views."""
from __future__ import annotations

import copy
from typing import Any


def merge_settlement_controls(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(current)
    previous_residents = {str(item.get("id")): item for item in previous.get("residents", [])}
    for resident in merged.get("residents", []):
        prior = previous_residents.get(str(resident.get("id")))
        if prior is None:
            continue
        resident["assignment"] = prior.get("assignment", resident.get("assignment"))
        resident["drafted"] = bool(prior.get("drafted", resident.get("drafted", False)))
        if "squad_role" in prior:
            resident["squad_role"] = prior["squad_role"]

    previous_rooms = {str(item.get("id")): item for item in previous.get("rooms", [])}
    merged_rooms: list[dict[str, Any]] = []
    for room in merged.get("rooms", []):
        prior = previous_rooms.get(str(room.get("id")))
        if prior is not None:
            merged_room = copy.deepcopy(room)
            for key, value in prior.items():
                if key in {"id", "kind", "label"}:
                    continue
                merged_room[key] = copy.deepcopy(value)
            merged_room["priority"] = prior.get("priority", merged_room.get("priority", 3))
            merged_rooms.append(merged_room)
        else:
            merged_rooms.append(copy.deepcopy(room))
    merged["rooms"] = merged_rooms

    previous_jobs = {str(item.get("id")): item for item in previous.get("jobs", [])}
    merged_jobs: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    for job in merged.get("jobs", []):
        job_id = str(job.get("id"))
        prior = previous_jobs.get(job_id)
        if prior is not None:
            merged_job = copy.deepcopy(job)
            merged_job["priority"] = prior.get("priority", merged_job.get("priority", 3))
            merged_job["status"] = prior.get("status", merged_job.get("status", "idle"))
            merged_job["assignee_id"] = prior.get("assignee_id", merged_job.get("assignee_id"))
            merged_jobs.append(merged_job)
        else:
            merged_jobs.append(copy.deepcopy(job))
        seen_job_ids.add(job_id)
    for job in previous.get("jobs", []):
        job_id = str(job.get("id"))
        if job_id not in seen_job_ids:
            merged_jobs.append(copy.deepcopy(job))
    merged["jobs"] = merged_jobs

    merged["defense_posture"] = str(previous.get("defense_posture", merged.get("defense_posture", "normal")))
    merged["population"] = int(previous.get("population", merged.get("population", 0)))
    merged["needs"] = copy.deepcopy(previous.get("needs", merged.get("needs", {})))
    merged["economy"] = copy.deepcopy(previous.get("economy", merged.get("economy", {})))
    merged["alerts"] = copy.deepcopy(previous.get("alerts", merged.get("alerts", [])))
    merged["faction_pressure"] = copy.deepcopy(previous.get("faction_pressure", merged.get("faction_pressure", [])))
    merged["stockpiles"] = copy.deepcopy(previous.get("stockpiles", merged.get("stockpiles", [])))
    merged["construction_queue"] = copy.deepcopy(previous.get("construction_queue", merged.get("construction_queue", [])))
    merged["farm_plots"] = copy.deepcopy(previous.get("farm_plots", merged.get("farm_plots", [])))
    merged["seed_stock"] = copy.deepcopy(previous.get("seed_stock", merged.get("seed_stock", {})))
    merged["available_materials"] = copy.deepcopy(previous.get("available_materials", merged.get("available_materials", [])))
    merged["trap_positions"] = copy.deepcopy(previous.get("trap_positions", merged.get("trap_positions", {})))
    return merged


__all__ = ["merge_settlement_controls"]
