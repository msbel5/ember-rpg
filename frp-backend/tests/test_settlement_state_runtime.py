"""Targeted tests for realized settlement runtime state."""

from engine.api.campaign_runtime import CampaignRuntime


def test_created_campaign_contains_residents_jobs_rooms_and_pressure():
    runtime = CampaignRuntime(llm=lambda _prompt: "stub")
    context = runtime.create_campaign("Settler", adapter_id="fantasy_ember", seed=42)
    settlement = context.settlement_state
    assert settlement["residents"]
    assert settlement["jobs"]
    assert settlement["rooms"]
    assert settlement["faction_pressure"]
    assert settlement["needs"]["food"] >= 1
