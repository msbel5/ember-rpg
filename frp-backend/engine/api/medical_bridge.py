"""Medical command bridge: kernel medical authority for diagnose/treat/surgery."""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional

from engine.api.campaign.live_kernel import (
    _refresh_treatment_record,
    normalize_actor_medical_state,
    sync_actor_medical_runtime_state,
)
from engine.kernel.medical import (
    TreatmentRecord,
    TreatmentStep,
    WoundRecord,
    can_perform_step,
    check_lethal_conditions,
    create_treatment_record,
    determine_treatment_plan,
    perform_treatment_step,
    surgery_failure_chance,
)

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord

logger = logging.getLogger(__name__)


def maybe_handle_medical_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle diagnose/treat/surgery via kernel medical pipeline."""
    lower = command_text.lower().strip()
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return None
    if lower.startswith("diagnose"):
        return _handle_diagnose(actors, player, command_text[8:].strip() or "self")
    if lower.startswith("surgery "):
        return _handle_surgery(actors, player, command_text[8:].strip() or "self")
    if lower.startswith("treat "):
        return _handle_treat(actors, player, command_text[6:].strip() or "self")
    return None


def _handle_diagnose(
    actors: dict,
    doctor: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    target = _resolve_medical_target(actors, target_name, doctor)
    if target is None:
        return (f"No target '{target_name}' found to diagnose.", "medical", 0)
    if target.body_state is None:
        return (f"{target.identity.display_name} has no injuries to diagnose.", "medical", 0)

    normalize_actor_medical_state(target, sync_derived=False)
    wounds = list(target.raw_payload.get("wounds", []))
    tick = int(target.raw_payload.get("game_tick", 0))
    patient_id = target.identity.actor_id
    existing_records = {
        record.wound_id: record
        for record in target.raw_payload.get("treatment_records", [])
        if isinstance(record, TreatmentRecord)
    }
    summaries: list[str] = []
    treatment_records: list[TreatmentRecord] = []

    for wound in wounds:
        if not isinstance(wound, WoundRecord):
            continue
        record = _refresh_treatment_record(
            existing_records.get(wound.wound_id) or create_treatment_record(wound, patient_id, tick),
            wound,
            tick,
        )
        record.diagnosed = True
        setattr(wound, "diagnosed", True)
        if TreatmentStep.DIAGNOSIS not in record.steps_completed:
            record.steps_completed.insert(0, TreatmentStep.DIAGNOSIS)
        record.steps_completed = _dedupe_steps(record.steps_completed)
        record.steps_remaining = [
            step for step in determine_treatment_plan(wound)
            if step not in record.steps_completed
        ]
        if not record.steps_remaining and record.tick_completed is None:
            record.tick_completed = tick
        treatment_records.append(record)
        summaries.append(_wound_summary(wound, record))

    for part_id, part in target.body_state.parts.items():
        if part.current_hp < part.max_hp:
            covered = any(w.body_part_id == part_id for w in wounds if isinstance(w, WoundRecord))
            if not covered:
                summaries.append(f"{part_id}: {part.current_hp}/{part.max_hp} hp")

    target.raw_payload["treatment_records"] = treatment_records
    sync_actor_medical_runtime_state(target)
    lethal, reason = check_lethal_conditions(target)
    status = f"CRITICAL ({reason})" if lethal else "stable"
    summary = "; ".join(summaries[:5]) if summaries else "no visible wounds"
    logger.info("Diagnose %s: %d wounds, status=%s", patient_id, len(wounds), status)
    return (f"Diagnosis for {target.identity.display_name}: {summary}. Status: {status}.", "medical", 1)


def _handle_treat(
    actors: dict,
    doctor: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    target = _resolve_medical_target(actors, target_name, doctor)
    if target is None:
        return (f"No target '{target_name}' found to treat.", "medical", 0)

    normalize_actor_medical_state(target, sync_derived=False)
    records = target.raw_payload.get("treatment_records", [])
    if not records:
        return ("No treatment records. Diagnose the patient first.", "medical", 0)

    wounds = list(target.raw_payload.get("wounds", []))
    materials = _available_medical_materials(doctor)
    results: list[str] = []
    mutated = False
    for record in records:
        if not record.steps_remaining:
            continue
        wound = _find_wound(wounds, record.wound_id)
        if wound is None:
            continue
        for step in list(record.steps_remaining):
            can_do, missing = can_perform_step(doctor, step, materials)
            if not can_do:
                results.append(f"{step.name}: missing {', '.join(missing)}")
                break
            ok, msg = perform_treatment_step(
                doctor,
                target,
                wound,
                record,
                step,
                materials,
                random.random(),
            )
            mutated = True
            results.append(f"{step.name}: {msg}")
            if not ok:
                break
    if not results:
        return (f"No treatable wounds on {target.identity.display_name}.", "medical", 0)

    sync_actor_medical_runtime_state(target)
    logger.info("Treat %s: %s", target.identity.display_name, "; ".join(results))
    return (
        f"Treatment for {target.identity.display_name}: {'; '.join(results)}.",
        "medical",
        2 if mutated else 0,
    )


def _handle_surgery(
    actors: dict,
    doctor: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    target = _resolve_medical_target(actors, target_name, doctor)
    if target is None:
        return (f"No target '{target_name}' found for surgery.", "medical", 0)

    normalize_actor_medical_state(target, sync_derived=False)
    records = target.raw_payload.get("treatment_records", [])
    if not records:
        return ("No treatment records. Diagnose the patient first.", "medical", 0)

    wounds = list(target.raw_payload.get("wounds", []))
    materials = _available_medical_materials(doctor)
    failure = surgery_failure_chance(int(doctor.skills.get("surgery", doctor.skills.get("surgery_skill", 0))))
    results: list[str] = []
    attempted = False
    for record in records:
        if TreatmentStep.SURGERY not in record.steps_remaining:
            continue
        wound = _find_wound(wounds, record.wound_id)
        if wound is None:
            continue
        can_do, missing = can_perform_step(doctor, TreatmentStep.SURGERY, materials)
        if not can_do:
            results.append(f"Surgery blocked: missing {', '.join(missing)}")
            continue
        attempted = True
        ok, msg = perform_treatment_step(
            doctor,
            target,
            wound,
            record,
            TreatmentStep.SURGERY,
            materials,
            random.random(),
        )
        results.append(f"Surgery ({failure:.0%} failure chance): {msg}")
        if not ok:
            break
    if not results:
        return ("No wounds requiring surgery.", "medical", 0)

    sync_actor_medical_runtime_state(target)
    logger.info("Surgery on %s: %s", target.identity.display_name, "; ".join(results))
    return (
        f"Surgery on {target.identity.display_name}: {'; '.join(results)}.",
        "medical",
        2 if attempted else 0,
    )


def _resolve_medical_target(actors: dict, name: str, player: "ActorRecord") -> Optional["ActorRecord"]:
    if name.lower() in {"self", "me", "player"}:
        return player
    for actor in actors.values():
        if hasattr(actor, "identity") and name.lower() in actor.identity.display_name.lower():
            return actor
    return None


def _available_medical_materials(doctor: "ActorRecord") -> dict[str, int]:
    materials: dict[str, int] = {}
    for item in doctor.inventory:
        def_id = str(getattr(item, "item_def_id", ""))
        qty = int(getattr(item, "quantity", 1))
        tags = list(getattr(item, "tags", []))
        if "bandage" in def_id or "cloth" in def_id:
            materials["bandage"] = materials.get("bandage", 0) + qty
            materials["cloth"] = materials.get("cloth", 0) + qty
        if "soap" in def_id:
            materials["soap"] = materials.get("soap", 0) + qty
        if "water" in def_id:
            materials["water"] = materials.get("water", 0) + qty
            materials["clean_water"] = materials.get("clean_water", 0) + qty
        if "thread" in def_id or "suture" in def_id:
            materials["thread"] = materials.get("thread", 0) + qty
            materials["suture_thread"] = materials.get("suture_thread", 0) + qty
        if "knife" in def_id or "scalpel" in def_id or "blade" in def_id:
            materials["edged_tool"] = materials.get("edged_tool", 0) + qty
        if "splint" in def_id:
            materials["splint"] = materials.get("splint", 0) + qty
        for tag in tags:
            materials[str(tag)] = materials.get(str(tag), 0) + qty
    return materials


def _find_wound(wounds: list, wound_id: str) -> Optional[WoundRecord]:
    for wound in wounds:
        if isinstance(wound, WoundRecord) and wound.wound_id == wound_id:
            return wound
    return None


def _dedupe_steps(steps: list[TreatmentStep]) -> list[TreatmentStep]:
    deduped: list[TreatmentStep] = []
    seen: set[TreatmentStep] = set()
    for step in steps:
        if step in seen:
            continue
        seen.add(step)
        deduped.append(step)
    return deduped


def _wound_summary(wound: WoundRecord, record: TreatmentRecord) -> str:
    plan_names = [step.name for step in record.steps_remaining]
    wound_info = f"{wound.body_part_id}: {wound.damage_type} ({wound.damage_amount} dmg)"
    if wound.bleeding > 0:
        wound_info += f", bleeding={wound.bleeding}"
    if wound.open_wound:
        wound_info += ", open"
    if wound.fracture:
        wound_info += ", fracture"
    if "embedded_object" in wound.tags:
        wound_info += ", embedded object"
    infection = float(getattr(wound, "infection_risk", 0.0))
    if infection > 0:
        wound_info += f", infection risk={infection:.0%}"
    wound_info += f" -> plan: {', '.join(plan_names)}"
    return wound_info


__all__ = ["maybe_handle_medical_command"]
