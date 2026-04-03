from __future__ import annotations

from typing import Any

from engine.kernel.actor import ActorRecord, NeedState
from engine.kernel.colony_types import (
    ColonyPressureState,
    MORALE_CASCADE_TIERS,
    NEED_DEFS,
    ProductionLedger,
    QuestSeed,
    SHORTAGE_QUEST_MAP,
)


def decay_needs(actor: ActorRecord, tick_count: int = 1) -> NeedState:
    for need_id, need_def in NEED_DEFS.items():
        current = float(actor.needs.values.get(need_id, 100.0))
        actor.needs.values[need_id] = max(0.0, current - (need_def.decay_rate * max(0, int(tick_count))))
    mood, modifiers = compute_mood(actor.needs)
    actor.needs.mood = mood
    actor.needs.modifiers = dict(modifiers)
    return actor.needs


def fulfill_need(actor: ActorRecord, need_id: str, facility_quality: int = 0) -> float:
    if need_id not in NEED_DEFS:
        raise KeyError(need_id)
    need_def = NEED_DEFS[need_id]
    amount = need_def.fulfillment_base * (1.0 + (int(facility_quality) * 0.1))
    old_value = float(actor.needs.values.get(need_id, 0.0))
    actor.needs.values[need_id] = min(100.0, old_value + amount)
    mood, modifiers = compute_mood(actor.needs)
    actor.needs.mood = mood
    actor.needs.modifiers = dict(modifiers)
    return actor.needs.values[need_id] - old_value


def compute_mood(needs: NeedState) -> tuple[str, dict[str, Any]]:
    total_weight = sum(need_def.weight for need_def in NEED_DEFS.values())
    if total_weight <= 0:
        return "steady", {}
    weighted = 0.0
    for need_id, need_def in NEED_DEFS.items():
        weighted += float(needs.values.get(need_id, 100.0)) * need_def.weight
    average = weighted / total_weight
    for tier in MORALE_CASCADE_TIERS:
        if average >= float(tier.unrest_max):
            continue
        if average >= float(tier.unrest_min) or tier == MORALE_CASCADE_TIERS[-1]:
            return tier.tier, {
                "work_speed_mult": tier.work_speed_mult,
                "social_hostility": tier.social_hostility,
                "task_refusal": tier.task_refusal,
                "tantrum_risk": tier.tantrum_risk,
            }
    # Fallback: use thresholds from colony_config.
    from engine.data._shared import colony_config_registry
    thresholds = colony_config_registry().get("thresholds", {}).get("mood", {})
    if average >= float(thresholds.get("content", 75)):
        return "content", {"work_speed_mult": 1.0}
    if average >= float(thresholds.get("unhappy", 50)):
        return "unhappy", {"work_speed_mult": 0.8}
    if average >= float(thresholds.get("miserable", 25)):
        return "miserable", {"work_speed_mult": 0.5, "social_hostility": True, "task_refusal": True, "tantrum_risk": 0.02}
    return "breakdown", {"work_speed_mult": 0.2, "social_hostility": True, "task_refusal": True, "tantrum_risk": 0.10}


def apply_morale_cascade(actors: list[ActorRecord], unrest: int) -> None:
    tier = next(
        candidate
        for candidate in MORALE_CASCADE_TIERS
        if candidate.unrest_min <= int(unrest) < candidate.unrest_max
    )
    modifiers = {
        "work_speed_mult": tier.work_speed_mult,
        "social_hostility": tier.social_hostility,
        "task_refusal": tier.task_refusal,
        "tantrum_risk": tier.tantrum_risk,
    }
    for actor in actors:
        actor.needs.mood = tier.tier
        actor.needs.modifiers = dict(modifiers)


def quest_seeds_from_shortages(shortages: list[str]) -> list[QuestSeed]:
    seeds: list[QuestSeed] = []
    for shortage in shortages:
        template = SHORTAGE_QUEST_MAP.get(
            shortage,
            {"kind": shortage, "title": f"Address {shortage.title()} Pressure", "priority": 3},
        )
        seeds.append(
            QuestSeed(
                quest_id=f"pressure_{shortage}",
                kind=str(template["kind"]),
                title=str(template["title"]),
                priority=int(template["priority"]),
                source_pressure=str(shortage),
            )
        )
    return seeds


def pressure_tags_from_metrics(
    *,
    food: int,
    safety: int,
    morale: int,
    supply: int,
    housing: int,
    unrest: int,
) -> list[str]:
    from engine.data._shared import colony_config_registry
    cfg = colony_config_registry().get("pressure_tags", {})
    metrics = {"food": food, "safety": safety, "morale": morale, "supply": supply, "housing": housing, "unrest": unrest}
    pressure_tags: list[str] = []
    for tag, rule in cfg.items():
        if rule.get("type") == "compound":
            if all(_check_op(metrics.get(c["metric"], 0), c["operator"], c["threshold"]) for c in rule["conditions"]):
                pressure_tags.append(tag)
        else:
            if _check_op(metrics.get(rule["metric"], 0), rule["operator"], rule["threshold"]):
                pressure_tags.append(tag)
    return pressure_tags


def _check_op(value: int, operator: str, threshold: int) -> bool:
    v, t = int(value), int(threshold)
    if operator == "<": return v < t
    if operator == "<=": return v <= t
    if operator == ">": return v > t
    if operator == ">=": return v >= t
    return v == t


def room_morale_bonus(rooms: list[dict[str, Any]]) -> int:
    bonus = 0
    for room in rooms:
        if _room_has_required_furniture(room):
            bonus += 2
    return bonus


def production_ledger_from_settlement(settlement_state: dict[str, Any]) -> ProductionLedger:
    needs = dict(settlement_state.get("needs", {}))
    economy = dict(settlement_state.get("economy", {}))
    shortages: list[str] = []
    surpluses: list[str] = []
    from engine.data._shared import colony_config_registry
    shortage_threshold = int(colony_config_registry().get("thresholds", {}).get("shortage", 3))
    for resource_type in ("food", "materials", "security"):
        if int(needs.get(resource_type, 0)) >= shortage_threshold:
            shortages.append(resource_type)
        else:
            surpluses.append(resource_type)
    if float(economy.get("trade_balance", 0)) > 0:
        surpluses.append("trade")
    quest_seeds = quest_seeds_from_shortages(shortages)
    return ProductionLedger(
        economy=economy,
        shortages=shortages,
        surpluses=surpluses,
        quest_seeds=quest_seeds,
    )


def colony_pressure_from_settlement(settlement_state: dict[str, Any]) -> ColonyPressureState:
    needs = dict(settlement_state.get("needs", {}))
    alerts = list(settlement_state.get("alerts", []))
    residents = list(settlement_state.get("residents", []))
    rooms = list(settlement_state.get("rooms", []))
    drafted = sum(1 for resident in residents if resident.get("drafted"))
    beds = sum(int(room.get("beds", 0)) for room in rooms)
    historical_pressure = list(settlement_state.get("faction_pressure", []))
    ledger = production_ledger_from_settlement(settlement_state)
    active_farms = _active_farm_plot_count(list(settlement_state.get("farm_plots", [])))
    effective_food_need = max(0, int(needs.get("food", 0)) - active_farms)
    room_bonus = room_morale_bonus(rooms)

    food = max(0, 100 - effective_food_need * 15)
    safety = max(0, 100 - len(alerts) * 12 - int(needs.get("security", 0)) * 10 + drafted * 5)
    morale = max(0, 100 - len(alerts) * 8 - len(ledger.shortages) * 10 + room_bonus)
    supply = max(0, 100 - int(needs.get("materials", 0)) * 15 - len(settlement_state.get("construction_queue", [])) * 6)
    housing_gap = max(0, len(residents) - max(1, beds))
    housing = max(0, 100 - housing_gap * 20)
    unrest = min(100, len(alerts) * 14 + len(ledger.shortages) * 12 + len(historical_pressure) * 6)

    pressure_tags = pressure_tags_from_metrics(
        food=food,
        safety=safety,
        morale=morale,
        supply=supply,
        housing=housing,
        unrest=unrest,
    )
    return ColonyPressureState(
        food=food,
        safety=safety,
        morale=morale,
        supply=supply,
        housing=housing,
        unrest=unrest,
        shortages=ledger.shortages,
        pressure_tags=pressure_tags,
        quest_seeds=ledger.quest_seeds,
    )


def _room_has_required_furniture(room: dict[str, Any]) -> bool:
    if room.get("required_furniture_present") is False:
        return False
    if room.get("furnished") is False:
        return False
    if int(room.get("beds", 0)) > 0:
        return True
    if room.get("kind") in {"bedroom", "dormitory"}:
        return False
    return True


def _active_farm_plot_count(farm_plots: list[dict[str, Any]]) -> int:
    return sum(
        1
        for plot in farm_plots
        if bool(plot.get("active"))
        and str(plot.get("status", "active")) not in {"fallow", "unharvested"}
    )


__all__ = [
    "apply_morale_cascade",
    "colony_pressure_from_settlement",
    "compute_mood",
    "decay_needs",
    "fulfill_need",
    "pressure_tags_from_metrics",
    "production_ledger_from_settlement",
    "quest_seeds_from_shortages",
    "room_morale_bonus",
]
