from __future__ import annotations

import copy

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.live_kernel import ensure_kernel_runtime
from engine.world.consequence import PendingEffect
from engine.world.consequence import CascadeEngine
from engine.world import WorldState


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="CrimeTester", seed=91)
    ensure_kernel_runtime(context)
    if context.world_state is None:
        context.world_state = WorldState(game_id=context.campaign_id)
    if context.cascade_engine is None:
        context.cascade_engine = CascadeEngine()
    return runtime, context


def _install_crime_state(
    context,
    *,
    incident_type: str,
    wanted: bool,
    bounty: int,
    witness_count: int,
) -> None:
    context.kernel_runtime["game_state"].raw_payload["crime_state"] = {
        "wanted": bool(wanted),
        "active_bounty": int(bounty),
        "witness_count": int(witness_count),
        "last_incident": {
            "crime_type": incident_type,
            "severity": "high" if incident_type in {"murder", "assault"} else "medium",
            "target_id": "test_target",
            "target_name": "Test Target",
            "faction_id": "test_faction",
            "settlement_id": str(context.region_snapshot.region_id),
            "witnessed": int(witness_count) > 0,
            "reported": bool(wanted),
            "responses": [],
            "tick": 0,
        },
    }


def _install_cascade_and_flags(context, *, incident_type: str, bounty: int, witness_count: int) -> None:
    if context.world_state is None:
        raise AssertionError("Expected campaign world_state for crime flag persistence test")
    context.world_state.flags["wanted"] = True
    context.world_state.flags["bounty_active"] = int(bounty)
    context.world_state.flags["witness_count"] = int(witness_count)
    context.world_state.flags[f"{incident_type}_reported"] = True
    context.cascade_engine.pending_effects = [
        PendingEffect(
            rule_id=f"{incident_type}_consequence",
            effect={
                "effect_type": "set_flag",
                "target": f"{incident_type}_reported",
                "params": {"value": True},
                "description": f"{incident_type.title()} consequence applied",
            },
            trigger_at_day=2,
            trigger_at_hour=9.0,
            original_trigger={
                "type": incident_type,
                "witness_count": int(witness_count),
                "bounty": int(bounty),
            },
        )
    ]


def test_campaign_crime_state_payload_is_additive_and_stable() -> None:
    runtime, context = _make_campaign()
    _install_crime_state(context, incident_type="theft", wanted=True, bounty=25, witness_count=2)
    _install_cascade_and_flags(context, incident_type="theft", bounty=25, witness_count=2)

    first = runtime.snapshot(context.campaign_id, narrative="crime-a")["campaign"]["crime_state"]
    second = runtime.snapshot(context.campaign_id, narrative="crime-b")["campaign"]["crime_state"]

    assert first == second
    assert first["wanted"] is True
    assert first["active_bounty"] == 25
    assert first["witness_count"] == 2
    assert first["last_incident"]["crime_type"] == "theft"
    assert "crime_state" not in context.campaign_state


def test_save_load_preserves_crime_state_exactly() -> None:
    runtime, context = _make_campaign()
    _install_crime_state(context, incident_type="assault", wanted=True, bounty=80, witness_count=3)
    _install_cascade_and_flags(context, incident_type="assault", bounty=80, witness_count=3)

    before = runtime.snapshot(context.campaign_id, narrative="crime-before")["campaign"]["crime_state"]
    runtime.save_campaign(context.campaign_id, "crime_payload_slot", "CrimeTester")
    loaded = runtime.load_campaign("crime_payload_slot")
    after = runtime.snapshot(loaded.campaign_id, narrative="crime-after")["campaign"]["crime_state"]

    assert after == before
    assert "crime_state" not in loaded.campaign_state
    assert "crime_state" not in loaded.campaign_state.get("campaign", {})


def test_save_load_preserves_pending_cascade_effects_and_flags() -> None:
    runtime, context = _make_campaign()
    _install_crime_state(context, incident_type="murder", wanted=True, bounty=250, witness_count=4)
    _install_cascade_and_flags(context, incident_type="murder", bounty=250, witness_count=4)

    runtime.save_campaign(context.campaign_id, "crime_cascade_slot", "CrimeTester")
    loaded = runtime.load_campaign("crime_cascade_slot")
    loaded_crime = runtime.snapshot(loaded.campaign_id, narrative="crime-cascade")["campaign"]["crime_state"]

    assert len(getattr(loaded.cascade_engine, "pending_effects", [])) == 1
    assert loaded.cascade_engine.pending_effects[0].rule_id == "murder_consequence"
    assert loaded_crime["active_bounty"] == 250
    assert loaded.world_state.flags["wanted"] is True
    assert loaded.world_state.flags["bounty_active"] == 250
    assert loaded.world_state.flags["witness_count"] == 4
    assert loaded.world_state.flags["murder_reported"] is True


def test_post_crime_snapshots_stay_consistent_for_supported_incident_types() -> None:
    scenarios = [
        ("theft", 20, 1),
        ("assault", 75, 2),
        ("murder", 200, 3),
        ("trespass", 10, 1),
    ]

    for incident_type, bounty, witness_count in scenarios:
        runtime, context = _make_campaign()
        _install_crime_state(
            context,
            incident_type=incident_type,
            wanted=True,
            bounty=bounty,
            witness_count=witness_count,
        )
        _install_cascade_and_flags(
            context,
            incident_type=incident_type,
            bounty=bounty,
            witness_count=witness_count,
        )

        before = copy.deepcopy(runtime.snapshot(context.campaign_id, narrative=f"crime-{incident_type}-before")["campaign"]["crime_state"])
        runtime.save_campaign(context.campaign_id, f"crime_{incident_type}_slot", "CrimeTester")
        loaded = runtime.load_campaign(f"crime_{incident_type}_slot")
        after = runtime.snapshot(loaded.campaign_id, narrative=f"crime-{incident_type}-after")["campaign"]["crime_state"]

        assert after == before
        assert after["last_incident"]["crime_type"] == incident_type
        assert after["active_bounty"] == bounty
        assert after["witness_count"] == witness_count
