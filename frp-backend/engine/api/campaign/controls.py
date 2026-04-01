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
    for room in merged.get("rooms", []):
        prior = previous_rooms.get(str(room.get("id")))
        if prior is not None:
            room["priority"] = prior.get("priority", room.get("priority", 3))

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
    merged["stockpiles"] = copy.deepcopy(previous.get("stockpiles", merged.get("stockpiles", [])))
    merged["construction_queue"] = copy.deepcopy(previous.get("construction_queue", merged.get("construction_queue", [])))
    return merged


__all__ = ["merge_settlement_controls"]
