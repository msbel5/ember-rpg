from engine.kernel import (
    ColonyPressureState,
    JobRecord,
    ReactionDef,
    WorksiteRecord,
    colony_pressure_from_settlement,
    job_records_from_settlement,
    production_ledger_from_settlement,
    reaction_defs_from_settlement,
    worksite_records_from_settlement,
)


def _settlement_state() -> dict:
    return {
        "residents": [
            {"id": "player_commander", "drafted": False},
            {"id": "resident_1", "drafted": True},
            {"id": "resident_2", "drafted": False},
        ],
        "rooms": [
            {"id": "room_1", "kind": "house", "label": "House", "beds": 1, "workstations": ["forge"]},
            {"id": "room_2", "kind": "hall", "label": "Hall", "beds": 0, "workstations": ["bar_counter"]},
        ],
        "jobs": [
            {"id": "job_1", "kind": "forge", "priority": 4, "status": "idle", "assignee_id": None},
            {"id": "job_2", "kind": "hauling", "priority": 3, "status": "queued", "assignee_id": "resident_2"},
        ],
        "construction_queue": [{"id": "build_1", "kind": "warehouse", "priority": 5}],
        "needs": {"food": 4, "security": 3, "materials": 2},
        "alerts": ["Raid risk"],
        "faction_pressure": [{"event_type": "war", "summary": "Border war"}],
        "economy": {"trade_balance": 8},
    }


def test_job_records_from_settlement_promotes_legacy_jobs_and_queue():
    records = job_records_from_settlement(_settlement_state())

    assert all(isinstance(record, JobRecord) for record in records)
    assert any(record.kind == "forge" and record.skill_id == "smithing" for record in records)
    assert any("construction" in record.tags for record in records)


def test_reactions_and_worksites_are_derived_from_rooms():
    reactions = reaction_defs_from_settlement(_settlement_state())
    worksites = worksite_records_from_settlement(_settlement_state())

    assert all(isinstance(reaction, ReactionDef) for reaction in reactions)
    assert all(isinstance(worksite, WorksiteRecord) for worksite in worksites)
    assert any(reaction.worksite_kind == "forge" for reaction in reactions)
    assert any("forge_reaction" in worksite.reaction_ids for worksite in worksites)


def test_colony_pressure_tracks_shortages_unrest_and_quest_seeds():
    pressure = colony_pressure_from_settlement(_settlement_state())
    ledger = production_ledger_from_settlement(_settlement_state())

    assert isinstance(pressure, ColonyPressureState)
    assert "food" in pressure.shortages
    assert pressure.unrest > 0
    assert pressure.quest_seeds
    assert ledger.quest_seeds
