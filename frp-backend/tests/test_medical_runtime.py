from __future__ import annotations

from engine.api.campaign.live_kernel import ensure_kernel_runtime
from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.actor import WoundRecord
from engine.kernel.medical import InfectionState, PermanentConsequence, RecoveryState, TreatmentStep


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="MedicTester", seed=91)
    return runtime, context


def _player(context):
    return context.kernel_runtime["actors"]["player"]


def _injure_player(context, *, embedded: bool = False):
    player = _player(context)
    if player.body_state is None:
        raise AssertionError("Expected player body_state for medical runtime tests")
    wound = WoundRecord(
        wound_id=f"med_wound_{len(player.body_state.wounds) + 1}",
        body_part_id="left_leg",
        damage_type="slash",
        damage_amount=8,
        bleeding=5,
        pain=12,
        open_wound=True,
        fracture=True,
        tags=["embedded_object"] if embedded else [],
    )
    wound.infection_risk = 1.0
    wound.infection_level = 0.0
    wound.diagnosed = False
    player.body_state.apply_wound(wound)
    player.raw_payload["wounds"] = list(player.body_state.wounds)
    player.raw_payload["zone"] = "hospital"
    player.stats["hp"] = max(1, int(player.stats.get("hp", 20)) - int(wound.damage_amount))
    return player, wound


def _add_supplies(context, *item_ids: str) -> None:
    for item_id in item_ids:
        context.add_item({"id": item_id, "name": item_id.replace("_", " ").title(), "qty": 1}, merge=True)


def _treatment_row(payload: dict) -> dict:
    return payload["campaign"]["character_sheet"]["medical"]["treatment_records"][0]


def test_repeat_diagnose_preserves_completed_progress() -> None:
    runtime, context = _make_campaign()
    player, _ = _injure_player(context)
    player.skills.update({"diagnose": 1})
    _add_supplies(context, "soap", "clean_water")

    runtime.run_command(context.campaign_id, "diagnose self")
    treated = runtime.run_command(context.campaign_id, "treat self")
    rediagnosed = runtime.run_command(context.campaign_id, "diagnose self")

    treated_row = _treatment_row(treated)
    rediagnosed_row = _treatment_row(rediagnosed)

    assert "clean" in treated_row["steps_completed"]
    assert "clean" in rediagnosed_row["steps_completed"]
    assert "clean" not in rediagnosed_row["steps_remaining"]


def test_treat_advances_step_and_reduces_pending_state() -> None:
    runtime, context = _make_campaign()
    player, _ = _injure_player(context)
    player.skills.update({"diagnose": 1})
    _add_supplies(context, "soap", "clean_water")

    diagnosed = runtime.run_command(context.campaign_id, "diagnose self")
    treated = runtime.run_command(context.campaign_id, "treat self")

    assert treated["command_type"] == "medical"
    assert treated["campaign"]["character_sheet"]["medical"]["summary"]["pending_treatment_steps"] < (
        diagnosed["campaign"]["character_sheet"]["medical"]["summary"]["pending_treatment_steps"]
    )
    assert "clean" in _treatment_row(treated)["steps_completed"]


def test_surgery_blocked_without_required_tool_is_non_mutating() -> None:
    runtime, context = _make_campaign()
    player, _ = _injure_player(context, embedded=True)
    player.skills.update({"diagnose": 1, "surgery": 5})

    runtime.run_command(context.campaign_id, "diagnose self")
    record_before = _player(context).raw_payload["treatment_records"][0].to_dict()

    result = runtime.run_command(context.campaign_id, "surgery self")
    record_after = _player(context).raw_payload["treatment_records"][0].to_dict()

    assert result["command_type"] == "medical"
    assert "missing" in result["narrative"].lower()
    assert record_after == record_before


def test_rest_advances_infection_state_and_logs_summary() -> None:
    runtime, context = _make_campaign()
    player, _ = _injure_player(context)
    player.skills.update({"diagnose": 1})

    diagnosed = runtime.run_command(context.campaign_id, "diagnose self")
    before = diagnosed["campaign"]["character_sheet"]["medical"]["infections"][0]["infection_level"]

    rested = runtime.run_command(context.campaign_id, "rest")
    after = rested["campaign"]["character_sheet"]["medical"]["infections"][0]["infection_level"]

    assert after > before
    assert any(event["event_type"] == "infection_progress" for event in rested["generated_events"])


def test_long_rest_progresses_recovery_and_updates_hp() -> None:
    runtime, context = _make_campaign()
    player, wound = _injure_player(context)
    part = player.body_state.parts[wound.body_part_id]
    player.raw_payload["medical_recoveries"] = [
        RecoveryState(
            body_part_id=wound.body_part_id,
            current_hp=int(part.current_hp),
            max_hp=int(part.max_hp),
            treatment_quality=1.5,
            recuperation_bonus=0.1,
            ticks_since_last_heal=49,
        )
    ]
    baseline_part_hp = int(part.current_hp)
    baseline_actor_hp = int(player.stats.get("hp", 0))

    result = runtime.run_command(context.campaign_id, "long rest")
    recovery = result["campaign"]["character_sheet"]["medical"]["recoveries"][0]

    assert result["command_type"] == "rest"
    assert int(recovery["current_hp"]) > baseline_part_hp
    assert int(_player(context).stats.get("hp", 0)) > baseline_actor_hp


def test_save_load_preserves_medical_state_and_rehydration() -> None:
    runtime, context = _make_campaign()
    player, wound = _injure_player(context)
    runtime.run_command(context.campaign_id, "diagnose self")
    part = player.body_state.parts[wound.body_part_id]
    player.raw_payload["medical_infections"] = [
        InfectionState(wound_id=wound.wound_id, body_part_id=wound.body_part_id, infection_level=7.0)
    ]
    player.raw_payload["medical_recoveries"] = [
        RecoveryState(
            body_part_id=wound.body_part_id,
            current_hp=int(part.current_hp),
            max_hp=int(part.max_hp),
            treatment_quality=1.2,
            recuperation_bonus=0.1,
            ticks_since_last_heal=49,
        )
    ]
    player.raw_payload["permanent_consequences"] = [
        PermanentConsequence(
            consequence_id="scar_left_leg",
            kind="chronic_pain",
            body_part_id=wound.body_part_id,
            description="The leg still aches after hard marches.",
            stress_per_tick=0.5,
        )
    ]

    runtime.save_campaign(context.campaign_id, "medical_runtime_slot", "MedicTester")
    loaded = runtime.load_campaign("medical_runtime_slot")
    loaded_player = loaded.kernel_runtime["actors"]["player"]

    assert isinstance(loaded_player.raw_payload["treatment_records"][0].steps_completed[0], TreatmentStep)
    assert isinstance(loaded_player.raw_payload["medical_infections"][0], InfectionState)
    assert isinstance(loaded_player.raw_payload["medical_recoveries"][0], RecoveryState)
    assert isinstance(loaded_player.raw_payload["permanent_consequences"][0], PermanentConsequence)

    before = float(loaded_player.raw_payload["medical_infections"][0].infection_level)
    rested = runtime.run_command(loaded.campaign_id, "rest")
    after = rested["campaign"]["character_sheet"]["medical"]["infections"][0]["infection_level"]

    assert after > before
    assert rested["campaign"]["character_sheet"]["medical"]["permanent_consequences"]


def test_projection_rebuild_preserves_medical_state() -> None:
    runtime, context = _make_campaign()
    player, _ = _injure_player(context)
    player.skills.update({"diagnose": 1})
    diagnosed = runtime.run_command(context.campaign_id, "diagnose self")
    before = diagnosed["campaign"]["character_sheet"]["medical"]

    ensure_kernel_runtime(context, rebuild_projection=True)
    after = runtime.snapshot(context.campaign_id, narrative="medical-rebuild")["campaign"]["character_sheet"]["medical"]

    assert after["summary"]["active_wound_count"] == before["summary"]["active_wound_count"]
    assert len(after["treatment_records"]) == len(before["treatment_records"])
