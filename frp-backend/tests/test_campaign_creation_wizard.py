from __future__ import annotations

from types import SimpleNamespace

from engine.api.campaign_runtime import CampaignCreationContext
from engine.core.character_creation import CreationState
from tools.campaign_client import CampaignClient


class _DummyRuntime:
    def __init__(self) -> None:
        self.create_calls: list[dict] = []
        self.creation_flows: dict[str, CampaignCreationContext] = {}

    def create_campaign(self, **kwargs):
        self.create_calls.append(dict(kwargs))
        return SimpleNamespace(campaign_id="camp_1", recent_event_log=[{"summary": "Opening."}])

    def start_creation(self, *, player_name: str, adapter_id: str, profile_id: str, seed: int | None = None, location: str | None = None):
        state = CreationState(player_name=player_name, location=location)
        state.ensure_roll()
        context = CampaignCreationContext(
            state=state,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=seed or 0,
            location=location,
        )
        self.creation_flows[state.creation_id] = context
        return context

    def get_creation(self, creation_id: str):
        return self.creation_flows[creation_id]

    def answer_creation(self, creation_id: str, question_id: str, answer_id: str):
        context = self.creation_flows[creation_id]
        context.state.answer_question(question_id, answer_id)
        return context

    def reroll_creation(self, creation_id: str):
        context = self.creation_flows[creation_id]
        context.state.reroll()
        return context

    def save_creation_roll(self, creation_id: str):
        context = self.creation_flows[creation_id]
        context.state.save_current_roll()
        return context

    def swap_creation_roll(self, creation_id: str):
        context = self.creation_flows[creation_id]
        context.state.swap_rolls()
        return context

    def finalize_creation(self, creation_id: str, **kwargs):
        self.create_calls.append(dict(kwargs))
        self.creation_flows.pop(creation_id, None)
        return SimpleNamespace(campaign_id="camp_1", recent_event_log=[{"summary": "Opening."}])

    def snapshot(self, campaign_id: str, narrative: str = ""):
        return {
            "campaign_id": campaign_id,
            "narrative": narrative,
            "campaign": {
                "player": {
                    "name": "Ada",
                    "player_class": "rogue",
                    "alignment": "CN",
                    "skill_proficiencies": ["stealth", "deception"],
                    "stats": {
                        "MIG": 8,
                        "END": 10,
                        "AGI": 16,
                        "MND": 12,
                        "INS": 14,
                        "PRE": 10,
                    },
                    "hp": 12,
                    "max_hp": 12,
                    "ap": {"current": 3, "max": 3},
                },
                "world": {
                    "adapter_id": "scifi_frontier",
                    "profile_id": "standard",
                },
                "settlement": {"name": "Frontier Outpost"},
            },
        }

    def run_command(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def get_current_region(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def get_current_settlement(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def save_campaign(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def list_campaign_saves(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def load_campaign(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def delete_campaign(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError


def test_campaign_creation_wizard_uses_runtime_creation_flow():
    runtime = _DummyRuntime()
    client = CampaignClient(runtime=runtime)

    creation = client.start_creation("Ada", adapter_id="scifi_frontier", profile_id="standard", seed=7)
    assert creation["creation_id"]
    assert len(creation["questions"]) >= 1
    assert len(creation["current_roll"]) == 6

    first_question = creation["questions"][0]
    first_answer = first_question["answers"][0]["id"]
    answered = client.answer_creation(creation["creation_id"], first_question["id"], first_answer)
    assert answered["answers"]

    saved = client.save_creation_roll(creation["creation_id"])
    assert saved["saved_roll"] is not None

    rerolled = client.reroll_creation(creation["creation_id"], seed=11)
    assert rerolled["current_roll"] != saved["saved_roll"]

    swapped = client.swap_creation_roll(creation["creation_id"])
    assert swapped["current_roll"] == saved["saved_roll"]

    final = client.finalize_creation(
        creation["creation_id"],
        player_name="Ada",
        player_class="rogue",
        alignment="CN",
        skill_proficiencies=["stealth", "deception"],
        assigned_stats={
            "MIG": 8,
            "END": 10,
            "AGI": 16,
            "MND": 12,
            "INS": 14,
            "PRE": 10,
        },
        adapter_id="scifi_frontier",
        profile_id="standard",
        seed=7,
    )

    assert runtime.create_calls[-1]["adapter_id"] == "scifi_frontier"
    assert runtime.create_calls[-1]["player_class"] == "rogue"
    assert final["character_sheet"]["name"] == "Ada"
    assert final["creation_state"]["final_class"] == "rogue"
    assert final["creation_state"]["final_alignment"] == "CN"
    assert "stealth" in final["character_sheet"]["skills"]
