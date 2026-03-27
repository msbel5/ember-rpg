"""Thin campaign facade for terminal tools and targeted tests."""
from __future__ import annotations

from typing import Any, Callable, Optional

from engine.api.campaign_runtime import CampaignRuntime
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
        return self.runtime.snapshot(context.campaign_id, narrative=narrative)

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self.runtime.snapshot(campaign_id)

    def submit_command(
        self,
        campaign_id: str,
        input_text: str,
        shortcut: str | None = None,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.runtime.run_command(campaign_id, input_text, shortcut, args)

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
        return self.runtime.snapshot(context.campaign_id, narrative=f"Loaded campaign from {save_id}.")

    def delete_campaign(self, campaign_id: str) -> dict[str, Any]:
        self.runtime.delete_campaign(campaign_id)
        return {"status": "deleted", "campaign_id": campaign_id}
