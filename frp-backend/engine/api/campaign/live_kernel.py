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
)

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
from engine.kernel.game_state import normalize_party_state

if TYPE_CHECKING:
    from .context import CampaignContext

_RUNTIME_MEDICAL_KEYS = (
    "wounds",
    "treatment_records",
    "medical_infections",
    "medical_recoveries",
    "permanent_consequences",
)
_PARTY_CAPABLE_ACTOR_TYPES = {"npc", "creature"}
_NON_PARTY_ROLE_HINTS = {"cabinet", "cauldron", "table", "oven", "bench", "chair", "bed", "pew", "sack"}


def _is_party_capable_actor(actor: ActorRecord | None) -> bool:
    if actor is None:
        return False
    actor_id = str(getattr(getattr(actor, "identity", None), "actor_id", "")).strip()
    if not actor_id or actor_id == "player":
        return False
    actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip()
    if actor_type not in _PARTY_CAPABLE_ACTOR_TYPES:
        return False
    role_hint = str(actor.raw_payload.get("role", actor.raw_payload.get("template", ""))).lower().strip()
    if role_hint in _NON_PARTY_ROLE_HINTS:
        return False
    if any(
        bool(actor.raw_payload.get(key))
        for key in ("companion_roster", "party_member", "active_party_member", "reserve_party_member")
    ):
        return True
    return str(actor.raw_payload.get("source", "")).lower().strip() != "campaign_entity"


def ensure_kernel_runtime(context: "CampaignContext", *, rebuild_projection: bool = False) -> dict[str, Any]:
    if context.kernel_runtime and not rebuild_projection:
        _sync_runtime_from_context(context, context.kernel_runtime)
        context.player = context.kernel_runtime.get("actors", {}).get("player", context.player)
        return context.kernel_runtime
    meta = dict(context.campaign_state.get("campaign") or {})
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
                context,
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
    _sync_runtime_from_context(context, runtime)
    context.player = runtime.get("actors", {}).get("player", context.player)
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
    _sync_runtime_from_context(context, runtime)
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
    # ── Post-tick: promote conditions, check level-up ──────────
    for actor in actors:
        # Promote raw string conditions to ConditionRecord objects.
        _ = actor.condition_names  # noqa: property triggers in-place promotion
    player = runtime["actors"].get("player")
    if player is not None:
        events.extend(_check_level_up(player))
    refresh_runtime_views(context, runtime)
    context.player = runtime.get("actors", {}).get("player", context.player)
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

    raw_progression = player.raw_payload.get("progression")
    if isinstance(raw_progression, dict):
        try:
            progression_state = ProgressionState.from_dict(raw_progression)
        except Exception:  # pragma: no cover - malformed saves should fall back safely
            progression_state = ProgressionState(actor_id=player.identity.actor_id)
    else:
        progression_state = ProgressionState(actor_id=player.identity.actor_id)
    progression_state.actor_id = player.identity.actor_id
    progression_state.xp = int(player.raw_payload.get("xp", progression_state.xp))
    progression_state.level = int(player.raw_payload.get("level", progression_state.level or 1))
    progression_state.classes = list(progression_state.classes or [class_id])
    if class_id not in progression_state.classes:
        progression_state.classes.append(class_id)
    if not progression_state.class_levels:
        progression_state.class_levels = {class_id: progression_state.level}
    else:
        progression_state.class_levels[class_id] = int(player.raw_payload.get("level", progression_state.class_levels.get(class_id, progression_state.level)))
    progression_state.bab = int(player.raw_payload.get("bab", progression_state.bab))
    progression_state.saves = {
        str(key): int(value)
        for key, value in dict(player.raw_payload.get("saves", progression_state.saves)).items()
    }
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
        actors = {actor.identity.actor_id: actor for actor in [ActorRecord.from_dict(dict(item)) for item in saved_payload]}
        for actor in actors.values():
            normalize_actor_medical_state(actor, sync_derived=True)
        return actors
    actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }
    for actor in actors.values():
        normalize_actor_medical_state(actor, sync_derived=True)
    return actors


def _sync_runtime_from_context(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    fresh_actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }
    # Preserve runtime-owned actors that are not part of the authored region
    # projection yet, such as recruited companions and runtime-only NPCs.
    merged: dict[str, ActorRecord] = {
        actor_id: actor
        for actor_id, actor in dict(runtime.get("actors", {})).items()
    }
    for actor_id, fresh_actor in fresh_actors.items():
        existing = merged.get(actor_id)
        if existing is None:
            merged[actor_id] = fresh_actor
            continue
        _merge_actor(existing, fresh_actor)
        normalize_actor_medical_state(existing, sync_derived=True)
        merged[actor_id] = existing
    for actor_id, actor in merged.items():
        if actor_id not in fresh_actors:
            normalize_actor_medical_state(actor, sync_derived=True)
    runtime["actors"] = merged
    runtime["game_state"].actors = dict(merged)
    normalize_party_state(runtime["game_state"])
    existing_party = [str(actor_id) for actor_id in list(getattr(runtime["game_state"], "party", [])) if str(actor_id)]
    requested_party = [str(actor_id) for actor_id in list(context.campaign_state.get("party", [])) if str(actor_id)]
    party: list[str] = []
    for actor_id in existing_party + requested_party:
        if actor_id == "player":
            if actor_id in merged and actor_id not in party:
                party.append(actor_id)
            continue
        if actor_id in merged and _is_party_capable_actor(merged.get(actor_id)) and actor_id not in party:
            party.append(actor_id)
    if "player" in merged and "player" not in party:
        party.insert(0, "player")
    runtime["game_state"].party = party
    existing_reserves = [
        str(actor_id)
        for actor_id in list(getattr(runtime["game_state"], "inactive_npcs", []))
        if str(actor_id)
        and str(actor_id) in merged
        and str(actor_id) not in party
        and _is_party_capable_actor(merged.get(str(actor_id)))
    ]
    requested_reserves = [
        str(actor_id)
        for actor_id in list(context.campaign_state.get("reserve_party_members", []))
        if str(actor_id)
        and str(actor_id) in merged
        and str(actor_id) not in party
        and _is_party_capable_actor(merged.get(str(actor_id)))
    ]
    roster_reserves = [
        actor_id
        for actor_id, actor in merged.items()
        if actor_id not in party
        and actor_id != "player"
        and _is_party_capable_actor(actor)
        and bool(actor.raw_payload.get("companion_roster"))
    ]
    inactive: list[str] = []
    for actor_id in existing_reserves + requested_reserves + roster_reserves:
        if actor_id not in inactive:
            inactive.append(actor_id)
    runtime["game_state"].inactive_npcs = inactive
    normalize_party_state(runtime["game_state"])
    context.campaign_state["party_tactics"] = dict(getattr(runtime["game_state"], "party_tactics", {}))
    context.campaign_state["party"] = list(getattr(runtime["game_state"], "party", []))
    context.campaign_state["reserve_party_members"] = list(getattr(runtime["game_state"], "inactive_npcs", []))
    for actor_id, actor in merged.items():
        eligible = _is_party_capable_actor(actor)
        preserve_roster_flag = bool(actor.raw_payload.get("companion_roster")) and eligible
        is_active = eligible and actor_id in context.campaign_state["party"] and actor_id != "player"
        is_reserve = eligible and actor_id in context.campaign_state["reserve_party_members"]
        if actor_id != "player":
            actor.raw_payload["companion_roster"] = bool(is_active or is_reserve or preserve_roster_flag)
            actor.raw_payload["party_member"] = is_active
            actor.raw_payload["active_party_member"] = is_active
            actor.raw_payload["reserve_party_member"] = is_reserve
        if eligible and (is_active or is_reserve or preserve_roster_flag):
            actor.raw_payload["party_tactic_mode"] = str(getattr(runtime["game_state"], "party_tactics", {}).get(actor_id, "balanced"))
        elif actor_id != "player":
            actor.raw_payload.pop("party_tactic_mode", None)
    context.player = merged.get("player", context.player)


def _merge_actor(target: ActorRecord, fresh: ActorRecord) -> None:
    target.action_points = fresh.action_points
    target.max_action_points = fresh.max_action_points
    target.turn_resources = dict(fresh.turn_resources)
    # Runtime actors own their live coordinates. Region projection can rebuild
    # fresh shells each tick, but we must not snap actors back to authored spawn
    # points here or hazards/traps/combat movement will silently desync.
    if target.position is None:
        target.position = fresh.position
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
    preserved_medical = {
        key: target.raw_payload.get(key)
        for key in _RUNTIME_MEDICAL_KEYS
        if key in target.raw_payload
    }
    target.raw_payload.update(fresh.raw_payload)
    if preserved_xp is not None:
        target.raw_payload["xp"] = max(int(preserved_xp), int(target.raw_payload.get("xp", 0)))
    if preserved_level is not None:
        target.raw_payload["level"] = max(int(preserved_level), int(target.raw_payload.get("level", 1)))
    for key, value in preserved_medical.items():
        target.raw_payload[key] = value
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


def normalize_actor_medical_state(actor: ActorRecord, *, sync_derived: bool = False) -> None:
    """Normalize an actor's medical raw payload into typed kernel objects."""
    from engine.kernel.medical import InfectionState, PermanentConsequence, RecoveryState, TreatmentRecord

    body_wounds = list(getattr(getattr(actor, "body_state", None), "wounds", []) or [])
    raw_wounds = actor.raw_payload.get("wounds", [])
    wounds = _merge_wounds(raw_wounds, body_wounds)
    actor.raw_payload["wounds"] = wounds
    if actor.body_state is not None:
        actor.body_state.wounds = wounds

    actor.raw_payload["treatment_records"] = _normalize_records(
        actor.raw_payload.get("treatment_records", []),
        TreatmentRecord,
    )
    actor.raw_payload["medical_infections"] = _normalize_records(
        actor.raw_payload.get("medical_infections", []),
        InfectionState,
    )
    actor.raw_payload["medical_recoveries"] = _normalize_records(
        actor.raw_payload.get("medical_recoveries", []),
        RecoveryState,
    )
    actor.raw_payload["permanent_consequences"] = _normalize_records(
        actor.raw_payload.get("permanent_consequences", []),
        PermanentConsequence,
    )

    if sync_derived:
        sync_actor_medical_runtime_state(actor)


def sync_actor_medical_runtime_state(actor: ActorRecord) -> None:
    """Refresh treatment, infection, and recovery state for an actor."""
    from engine.kernel.medical import InfectionState, RecoveryState

    normalize_actor_medical_state(actor, sync_derived=False)
    wounds: list = list(actor.raw_payload.get("wounds", []))
    current_tick = int(actor.raw_payload.get("game_tick", 0))
    record_map = {record.wound_id: record for record in actor.raw_payload.get("treatment_records", [])}
    refreshed_records = []
    for wound in wounds:
        record = record_map.get(wound.wound_id)
        if record is None:
            continue
        refreshed_records.append(_refresh_treatment_record(record, wound, current_tick))
    actor.raw_payload["treatment_records"] = refreshed_records

    existing_infections = {
        state.wound_id: state
        for state in actor.raw_payload.get("medical_infections", [])
        if isinstance(state, InfectionState)
    }
    infections = []
    wound_ids = {wound.wound_id for wound in wounds}
    for wound in wounds:
        record = next((item for item in refreshed_records if item.wound_id == wound.wound_id), None)
        state = _sync_infection_state(wound, record, existing_infections.get(wound.wound_id))
        if state is not None:
            infections.append(state)
    for wound_id, state in existing_infections.items():
        if wound_id not in wound_ids:
            infections.append(state)
    actor.raw_payload["medical_infections"] = infections

    existing_recoveries = {
        state.body_part_id: state
        for state in actor.raw_payload.get("medical_recoveries", [])
        if isinstance(state, RecoveryState)
    }
    recoveries = []
    body_state = getattr(actor, "body_state", None)
    if body_state is not None:
        treatment_by_part: dict[str, float] = {}
        for wound in wounds:
            record = next((item for item in refreshed_records if item.wound_id == wound.wound_id), None)
            if record is None:
                continue
            treatment_by_part[wound.body_part_id] = max(
                float(treatment_by_part.get(wound.body_part_id, 0.0)),
                float(record.treatment_quality),
            )
        for part_id, part in body_state.parts.items():
            existing = existing_recoveries.get(part_id)
            if int(part.current_hp) >= int(part.max_hp) and existing is None:
                continue
            recovery = existing or RecoveryState(
                body_part_id=part_id,
                current_hp=int(part.current_hp),
                max_hp=int(part.max_hp),
            )
            recovery.current_hp = int(part.current_hp)
            recovery.max_hp = int(part.max_hp)
            recovery.recuperation_bonus = max(float(recovery.recuperation_bonus), _recuperation_bonus(actor))
            recovery.treatment_quality = max(
                float(recovery.treatment_quality),
                float(treatment_by_part.get(part_id, 0.5)),
            )
            if int(recovery.current_hp) < int(recovery.max_hp):
                recoveries.append(recovery)
        for part_id, recovery in existing_recoveries.items():
            if part_id not in body_state.parts:
                recoveries.append(recovery)
    actor.raw_payload["medical_recoveries"] = recoveries


def build_medical_payload(actor: ActorRecord) -> dict[str, Any]:
    """Project structured medical state for campaign payloads."""
    from engine.kernel.medical import InfectionState, PermanentConsequence, RecoveryState, TreatmentRecord

    normalize_actor_medical_state(actor, sync_derived=True)
    wounds: list = list(actor.raw_payload.get("wounds", []))
    records: list[TreatmentRecord] = list(actor.raw_payload.get("treatment_records", []))
    infections: list[InfectionState] = list(actor.raw_payload.get("medical_infections", []))
    recoveries: list[RecoveryState] = list(actor.raw_payload.get("medical_recoveries", []))
    consequences: list[PermanentConsequence] = list(actor.raw_payload.get("permanent_consequences", []))

    from engine.kernel.medical import check_lethal_conditions

    lethal, reason = check_lethal_conditions(actor)
    active_infections = [
        state
        for state in infections
        if float(state.infection_level) > 0.0 or state.fever or state.organ_damage or state.lethal
    ]
    recovering_parts = [state.body_part_id for state in recoveries if int(state.current_hp) < int(state.max_hp)]
    aftercare: list[str] = []
    for state in recoveries:
        if int(state.current_hp) < int(state.max_hp):
            aftercare.append(f"{state.body_part_id} recovering ({int(state.current_hp)}/{int(state.max_hp)} hp).")
    for infection in active_infections:
        aftercare.append(
            f"Monitor {infection.body_part_id} for infection ({float(infection.infection_level):.2f}).",
        )
    if consequences:
        aftercare.extend(f"{entry.body_part_id}: {entry.description}" for entry in consequences)

    if lethal:
        status = f"critical:{reason}"
    elif active_infections:
        status = "infected"
    elif wounds or records or recoveries:
        status = "recovering"
    else:
        status = "stable"

    return {
        "summary": {
            "status": status,
            "active_wound_count": len(wounds),
            "pending_treatment_steps": sum(len(record.steps_remaining) for record in records),
            "infection_count": len(active_infections),
            "recovering_parts": recovering_parts,
            "aftercare": aftercare,
        },
        "wounds": [
            {
                "wound_id": wound.wound_id,
                "body_part_id": wound.body_part_id,
                "damage_type": wound.damage_type,
                "damage_amount": int(wound.damage_amount),
                "bleeding": int(wound.bleeding),
                "pain": int(wound.pain),
                "open_wound": bool(wound.open_wound),
                "fracture": bool(wound.fracture),
                "infected": bool(getattr(wound, "infected", False)),
                "untreated": bool(wound.untreated),
                "destroyed": bool(wound.destroyed),
                "crippled": bool(wound.crippled),
                "infection_risk": float(getattr(wound, "infection_risk", 0.0)),
            }
            for wound in wounds
        ],
        "treatment_records": [
            {
                "wound_id": record.wound_id,
                "patient_id": record.patient_id,
                "doctor_id": record.doctor_id,
                "diagnosed": bool(record.diagnosed),
                "steps_completed": [step.name.lower() for step in record.steps_completed],
                "steps_remaining": [step.name.lower() for step in record.steps_remaining],
                "infection_level": float(record.infection_level),
                "infection_rate": float(record.infection_rate),
                "treatment_quality": float(record.treatment_quality),
                "tick_started": int(record.tick_started),
                "tick_completed": record.tick_completed,
            }
            for record in records
        ],
        "infections": [
            {
                "wound_id": infection.wound_id,
                "body_part_id": infection.body_part_id,
                "infection_level": float(infection.infection_level),
                "cleaned": bool(infection.cleaned),
                "fever": bool(infection.fever),
                "organ_damage": bool(infection.organ_damage),
                "lethal": bool(infection.lethal),
            }
            for infection in infections
        ],
        "recoveries": [
            {
                "body_part_id": recovery.body_part_id,
                "current_hp": int(recovery.current_hp),
                "max_hp": int(recovery.max_hp),
                "treatment_quality": float(recovery.treatment_quality),
                "recuperation_bonus": float(recovery.recuperation_bonus),
                "ticks_since_last_heal": int(recovery.ticks_since_last_heal),
            }
            for recovery in recoveries
        ],
        "permanent_consequences": [
            {
                "consequence_id": consequence.consequence_id,
                "kind": consequence.kind,
                "body_part_id": consequence.body_part_id,
                "description": consequence.description,
                "mobility_penalty": int(consequence.mobility_penalty),
                "stress_per_tick": float(consequence.stress_per_tick),
                "stat_modifiers": dict(consequence.stat_modifiers),
            }
            for consequence in consequences
        ],
    }


def _merge_wounds(raw_entries: list[Any], body_entries: list[Any]) -> list[Any]:
    from engine.kernel.medical import WoundRecord

    merged: list[Any] = []
    seen: set[str] = set()
    for entry in list(raw_entries or []) + list(body_entries or []):
        wound = entry if isinstance(entry, WoundRecord) else WoundRecord.from_dict(dict(entry)) if isinstance(entry, dict) else None
        if wound is None or wound.wound_id in seen:
            continue
        seen.add(wound.wound_id)
        merged.append(wound)
    return merged


def _normalize_records(entries: list[Any], cls: type) -> list[Any]:
    key_name = "body_part_id" if cls.__name__ == "RecoveryState" else "consequence_id" if cls.__name__ == "PermanentConsequence" else "wound_id"
    normalized: list[Any] = []
    seen: set[str] = set()
    for entry in entries or []:
        item = entry if isinstance(entry, cls) else cls.from_dict(dict(entry)) if isinstance(entry, dict) else None
        if item is None:
            continue
        key = str(getattr(item, key_name, ""))
        if not key or key in seen:
            continue
        if cls.__name__ == "TreatmentRecord":
            item.steps_completed = _dedupe_steps(item.steps_completed)
            item.steps_remaining = _dedupe_steps(
                [step for step in item.steps_remaining if step not in item.steps_completed],
            )
        if cls.__name__ == "InfectionState":
            from engine.kernel.medical import tick_infection

            tick_infection(item, 0)
        seen.add(key)
        normalized.append(item)
    return normalized


def _dedupe_steps(steps: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[Any] = set()
    for step in steps:
        if step in seen:
            continue
        seen.add(step)
        deduped.append(step)
    return deduped


def _refresh_treatment_record(record: Any, wound: Any, current_tick: int) -> Any:
    from engine.kernel.medical import TreatmentStep, determine_treatment_plan

    plan = determine_treatment_plan(wound)
    diagnosed = bool(record.diagnosed or getattr(wound, "diagnosed", False))
    completed = _dedupe_steps(record.steps_completed)
    if diagnosed and TreatmentStep.DIAGNOSIS not in completed:
        completed.insert(0, TreatmentStep.DIAGNOSIS)
    remaining = [step for step in plan if step not in completed]

    record.diagnosed = diagnosed
    record.steps_completed = completed
    record.steps_remaining = remaining
    record.infection_level = max(float(record.infection_level), float(getattr(wound, "infection_level", 0.0)))
    record.infection_rate = float(getattr(wound, "infection_risk", record.infection_rate))
    record.treatment_quality = max(float(record.treatment_quality), 0.5)
    if int(record.tick_started) <= 0:
        record.tick_started = int(current_tick)
    record.tick_completed = int(current_tick) if not remaining else None

    setattr(wound, "diagnosed", record.diagnosed)
    setattr(wound, "infection_risk", record.infection_rate)
    setattr(wound, "infection_level", record.infection_level)
    return record


def _sync_infection_state(wound: Any, record: Any, existing: Any) -> Any:
    from engine.kernel.medical import InfectionState, TreatmentStep, tick_infection

    infection_level = float(getattr(wound, "infection_level", 0.0))
    infection_risk = float(getattr(wound, "infection_risk", 0.0))
    if record is not None:
        infection_level = max(infection_level, float(record.infection_level))
        infection_risk = max(infection_risk, float(record.infection_rate))
    should_track = bool(existing) or bool(wound.open_wound) or bool(wound.infected) or infection_level > 0.0 or infection_risk > 0.0
    if not should_track:
        return None
    state = existing or InfectionState(wound_id=wound.wound_id, body_part_id=wound.body_part_id)
    state.body_part_id = wound.body_part_id
    state.infection_level = max(float(state.infection_level), infection_level)
    cleaned = bool(state.cleaned)
    if record is not None and TreatmentStep.CLEAN in record.steps_completed:
        cleaned = True
    if infection_risk <= 0.1 and infection_risk > 0.0:
        cleaned = True
    state.cleaned = cleaned
    tick_infection(state, 0)
    wound.infected = state.infection_level > 0.0 or state.fever or state.organ_damage or state.lethal
    setattr(wound, "infection_level", state.infection_level)
    setattr(wound, "infection_risk", infection_risk)
    if record is not None:
        record.infection_level = max(float(record.infection_level), float(state.infection_level))
        record.infection_rate = infection_risk
    return state


def _recuperation_bonus(actor: ActorRecord) -> float:
    return max(0.0, float(actor.stats.get("recuperation", 0)) / 100.0)


def _medical_tick_events(actors: list, current_tick: int) -> list[dict[str, Any]]:
    """Advance infection and recovery states for all actors."""
    from engine.kernel.medical import InfectionState, RecoveryState, tick_infection, tick_recovery

    events: list[dict[str, Any]] = []
    for actor in actors:
        normalize_actor_medical_state(actor, sync_derived=True)
        wounds_by_id = {
            wound.wound_id: wound
            for wound in actor.raw_payload.get("wounds", [])
        }
        for infection in actor.raw_payload.get("medical_infections", []):
            if isinstance(infection, InfectionState):
                prev = infection.infection_level
                tick_infection(infection, 1)
                wound = wounds_by_id.get(infection.wound_id)
                if wound is not None:
                    wound.infected = infection.infection_level > 0.0 or infection.fever or infection.organ_damage or infection.lethal
                    setattr(wound, "infection_level", infection.infection_level)
                if infection.infection_level > prev:
                    events.append({
                        "event_type": "infection_progress",
                        "summary": f"{actor.identity.display_name}: infection advanced to {infection.infection_level:.0%}.",
                        "actor_id": actor.identity.actor_id,
                    })
        for recovery in actor.raw_payload.get("medical_recoveries", []):
            if isinstance(recovery, RecoveryState):
                healed = tick_recovery(recovery, 1)
                if actor.body_state is not None and recovery.body_part_id in actor.body_state.parts:
                    part = actor.body_state.parts[recovery.body_part_id]
                    part.current_hp = min(int(part.max_hp), int(part.current_hp) + int(healed))
                    recovery.current_hp = int(part.current_hp)
                if healed > 0:
                    actor.stats["hp"] = min(
                        int(actor.stats.get("max_hp", actor.stats.get("hp", 0))),
                        int(actor.stats.get("hp", 0)) + int(healed),
                    )
                if healed > 0:
                    events.append({
                        "event_type": "medical_recovery",
                        "summary": f"{actor.identity.display_name}: recovered {healed} hp.",
                        "actor_id": actor.identity.actor_id,
                    })
    return events


__all__ = ["advance_kernel_runtime", "ensure_kernel_runtime", "serialize_kernel_runtime", "_check_level_up"]
