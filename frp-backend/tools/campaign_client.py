"""Thin campaign facade for terminal tools and targeted tests."""
from __future__ import annotations

from typing import Any, Callable, Optional

from engine.api.campaign_runtime import CampaignRuntime
from engine.core.character_creation import ABILITY_ORDER, assign_stats_to_class
from engine.llm import build_game_narrator


def _default_llm() -> Optional[Callable[[str], str]]:
    try:
        return build_game_narrator()
    except Exception:
        return None


class CampaignClient:
    """Expose API-shaped campaign methods without going through HTTP."""

    def __init__(self, runtime: CampaignRuntime | None = None, llm: Optional[Callable[[str], str]] = None):
        self.runtime = runtime or CampaignRuntime(llm=llm if llm is not None else _default_llm())

    def create_campaign(
        self,
        player_name: str,
        player_class: str = "warrior",
        adapter_id: str = "fantasy_ember",
        profile_id: str = "standard",
        seed: int | None = None,
    ) -> dict[str, Any]:
        context = self.runtime.create_campaign(
            player_name=player_name,
            player_class=player_class,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=seed,
        )
        narrative = context.recent_event_log[0]["summary"] if context.recent_event_log else ""
        snapshot = self.runtime.snapshot(context.campaign_id, narrative=narrative)
        snapshot["character_sheet"] = self.build_character_sheet(snapshot)
        return snapshot

    def start_creation(
        self,
        player_name: str,
        location: str = "",
        adapter_id: str = "fantasy_ember",
        profile_id: str = "standard",
        seed: int | None = None,
    ) -> dict[str, Any]:
        context = self.runtime.start_creation(
            player_name=player_name,
            adapter_id=adapter_id,
            profile_id=profile_id,
            seed=seed,
            location=location or None,
        )
        return self._creation_payload(context)

    def answer_creation(self, creation_id: str, question_id: str, answer_id: str) -> dict[str, Any]:
        return self._creation_payload(self.runtime.answer_creation(creation_id, question_id, answer_id))

    def reroll_creation(self, creation_id: str, seed: int | None = None) -> dict[str, Any]:
        _ = seed  # API parity for tests/tools; CampaignRuntime owns deterministic seed choice.
        return self._creation_payload(self.runtime.reroll_creation(creation_id))

    def save_creation_roll(self, creation_id: str) -> dict[str, Any]:
        return self._creation_payload(self.runtime.save_creation_roll(creation_id))

    def swap_creation_roll(self, creation_id: str) -> dict[str, Any]:
        return self._creation_payload(self.runtime.swap_creation_roll(creation_id))

    def finalize_creation(
        self,
        creation_id: str,
        player_name: str = "",
        player_class: str = "",
        alignment: str = "",
        skill_proficiencies: list[str] | None = None,
        assigned_stats: dict[str, int] | None = None,
        adapter_id: str = "",
        profile_id: str = "",
        location: str = "",
        seed: int | None = None,
    ) -> dict[str, Any]:
        state_snapshot = self._creation_payload(self.runtime.get_creation(creation_id))
        context = self.runtime.finalize_creation(
            creation_id,
            player_name=player_name or None,
            adapter_id=adapter_id or None,
            profile_id=profile_id or None,
            seed=seed,
            player_class=player_class or None,
            alignment=alignment or None,
            skill_proficiencies=skill_proficiencies,
            assigned_stats=assigned_stats,
            location=location or None,
        )
        narrative = context.recent_event_log[0]["summary"] if context.recent_event_log else ""
        snapshot = self.runtime.snapshot(context.campaign_id, narrative=narrative)
        built_sheet = self.build_character_sheet(snapshot, creation_state=state_snapshot)
        snapshot["creation_state"] = dict(state_snapshot)
        snapshot["creation_state"]["final_class"] = str(built_sheet["class"]).lower()
        snapshot["creation_state"]["final_alignment"] = str(built_sheet["alignment"])
        snapshot["creation_state"]["final_skills"] = list(built_sheet.get("skills", []))
        snapshot["creation_state"]["assigned_stats"] = {
            stat["ability"]: int(stat["value"])
            for stat in built_sheet.get("stats", [])
        }
        snapshot["campaign"]["creation_state"] = snapshot["creation_state"]
        snapshot["character_sheet"] = built_sheet
        return snapshot

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        snapshot = self.runtime.snapshot(campaign_id)
        snapshot["character_sheet"] = self.build_character_sheet(snapshot)
        return snapshot

    def submit_command(
        self,
        campaign_id: str,
        input_text: str,
        shortcut: str | None = None,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.runtime.run_command(campaign_id, input_text, shortcut, args)
        response["character_sheet"] = self.build_character_sheet(response)
        return response

    def get_region(self, campaign_id: str) -> dict[str, Any]:
        return self.runtime.get_current_region(campaign_id)

    def get_settlement(self, campaign_id: str) -> dict[str, Any]:
        return self.runtime.get_current_settlement(campaign_id)

    def save_campaign(
        self,
        campaign_id: str,
        slot_name: str = "",
        player_id: str = "",
    ) -> dict[str, Any]:
        return self.runtime.save_campaign(campaign_id, slot_name or None, player_id or None)

    def list_saves(self, campaign_id: str) -> list[dict[str, Any]]:
        return self.runtime.list_campaign_saves(campaign_id)

    def load_campaign(self, save_id: str) -> dict[str, Any]:
        context = self.runtime.load_campaign(save_id)
        snapshot = self.runtime.snapshot(context.campaign_id, narrative=f"Loaded campaign from {save_id}.")
        snapshot["character_sheet"] = self.build_character_sheet(snapshot)
        return snapshot

    def delete_campaign(self, campaign_id: str) -> dict[str, Any]:
        self.runtime.delete_campaign(campaign_id)
        return {"status": "deleted", "campaign_id": campaign_id}

    def build_character_sheet(
        self,
        snapshot: dict[str, Any],
        creation_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        campaign = dict(snapshot.get("campaign") or snapshot)
        player = dict(campaign.get("player") or snapshot.get("player") or {})
        creation = dict(creation_state or campaign.get("creation_state") or snapshot.get("creation_state") or {})
        if isinstance(campaign.get("character_sheet"), dict):
            backend_sheet = dict(campaign["character_sheet"])
            stats = []
            for stat in backend_sheet.get("stats", []):
                if not isinstance(stat, dict):
                    continue
                stats.append(
                    {
                        "ability": str(stat.get("id", stat.get("ability", ""))),
                        "label": str(stat.get("label", stat.get("id", ""))),
                        "value": int(stat.get("value", 10)),
                        "modifier": int(stat.get("modifier", 0)),
                    }
                )
            resources = dict(backend_sheet.get("resources", {}))
            return {
                "name": str(backend_sheet.get("name", "Adventurer")),
                "class": str(backend_sheet.get("class_name", backend_sheet.get("class", "warrior"))),
                "alignment": str(backend_sheet.get("alignment", "NN")),
                "skills": [
                    skill.get("label", skill.get("id", ""))
                    if isinstance(skill, dict)
                    else str(skill)
                    for skill in backend_sheet.get("skills", [])
                ],
                "stats": stats,
                "hp": dict(resources.get("hp", {"current": 0, "max": 1})),
                "ap": dict(resources.get("ap", {"current": 0, "max": 1})),
                "profile_id": str(snapshot.get("profile_id", creation.get("profile_id", "standard"))),
                "adapter_id": str(snapshot.get("adapter_id", creation.get("adapter_id", "fantasy_ember"))),
                "creation_summary": dict(backend_sheet.get("creation_summary", {})),
            }
        stats = dict(player.get("stats") or {})
        if not stats and creation.get("current_roll"):
            assigned = assign_stats_to_class(list(creation.get("current_roll") or []), str(player.get("player_class", "warrior")))
            stats = assigned
        ordered_stats: list[dict[str, Any]] = []
        for ability in ABILITY_ORDER:
            value = int(stats.get(ability, 10))
            ordered_stats.append(
                {
                    "ability": ability,
                    "value": value,
                    "modifier": (value - 10) // 2,
                }
            )
        current_ap = int(player.get("ap", {}).get("current", player.get("action_points", 0))) if isinstance(player.get("ap"), dict) else int(player.get("action_points", 0))
        max_ap = int(player.get("ap", {}).get("max", player.get("max_action_points", current_ap))) if isinstance(player.get("ap"), dict) else int(player.get("max_action_points", max(current_ap, 1)))
        return {
            "name": str(player.get("name", "Adventurer")),
            "class": str(player.get("player_class", "warrior")),
            "alignment": str(player.get("alignment", creation.get("recommended_alignment", "NN"))),
            "skills": list(player.get("skill_proficiencies") or creation.get("recommended_skills") or []),
            "stats": ordered_stats,
            "hp": {
                "current": int(player.get("hp", 0)),
                "max": int(player.get("max_hp", 1)),
            },
            "ap": {
                "current": current_ap,
                "max": max_ap,
            },
            "profile_id": str(snapshot.get("profile_id", creation.get("profile_id", "standard"))),
            "adapter_id": str(snapshot.get("adapter_id", creation.get("adapter_id", "fantasy_ember"))),
            "creation_summary": {
                "recommended_class": str(creation.get("recommended_class", player.get("player_class", "warrior"))),
                "recommended_alignment": str(creation.get("recommended_alignment", player.get("alignment", "NN"))),
                "current_roll": list(creation.get("current_roll") or []),
                "saved_roll": list(creation.get("saved_roll") or []),
            },
        }

    def _creation_payload(self, context) -> dict[str, Any]:
        payload = context.state.to_dict()
        payload["adapter_id"] = context.adapter_id
        payload["profile_id"] = context.profile_id
        payload["seed"] = int(context.seed)
        payload["location"] = context.location
        payload["character_sheet"] = self.build_character_sheet(
            {
                "player": {
                    "name": context.state.player_name,
                    "player_class": payload["recommended_class"],
                    "alignment": payload["recommended_alignment"],
                    "skill_proficiencies": payload["recommended_skills"],
                    "stats": assign_stats_to_class(payload["current_roll"] or context.state.ensure_roll(), payload["recommended_class"]),
                    "hp": 1,
                    "max_hp": 1,
                    "action_points": 0,
                    "max_action_points": 0,
                },
                "adapter_id": context.adapter_id,
                "profile_id": context.profile_id,
                "creation_state": payload,
            },
            creation_state=payload,
        )
        return payload
