from __future__ import annotations

from engine.api.campaign.dialog import clear_dialog_state
from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.quest_bridge import current_quest_offers
from _seed_robust_helpers import CURATED_AUTHORED_SEED, open_curated_authored_dialog


def test_curated_authored_town_loop_survives_save_load() -> None:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(
        player_name="AuthoredTownLoop",
        player_class="warrior",
        adapter_id="fantasy_ember",
        profile_id="standard",
        seed=CURATED_AUTHORED_SEED,
    )

    opened = open_curated_authored_dialog(runtime, context)
    talk = opened["response"]
    assert talk["command_type"] == "dialog"
    assert talk.get("dialog_npc") == opened["entity"]["name"]
    assert talk.get("dialog_options")

    topic_id = f"region.{context.region_snapshot.region_id}"
    ask_about = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="dialog",
        args={"action_id": "ask_about", "topic_id": topic_id},
    )
    assert ask_about["command_type"] == "dialog"
    assert ask_about["knowledge_view"]["ask_about"]["topic"]["topic_id"] == topic_id
    assert ask_about["knowledge_view"]["ask_about"]["response_type"] in {"fact", "rumor", "redirect", "refusal"}
    clear_dialog_state(context)

    authored_offer = next(
        offer
        for offer in current_quest_offers(context)
        if offer.get("source") == "authored_campaign" and offer.get("quest_id") == "tutorial_troubled_village"
    )
    accept = runtime.run_command(context.campaign_id, f"accept {authored_offer['quest_id']}")
    assert accept["command_type"] == "quest"

    active_quest = next(
        entry for entry in context.campaign_state.get("active_quests", []) if entry.get("quest_id") == authored_offer["quest_id"]
    )
    assert active_quest["source"] == "authored_campaign"
    assert active_quest["campaign_id"] == "tutorial_campaign"
    assert active_quest["act_id"] == "act_1"

    for objective in active_quest.get("objectives", []):
        objective["progress"] = int(objective.get("required", 1))
        objective["completed"] = True
        objective.setdefault("matched_ids", [])
    active_quest["report_ready"] = True
    active_quest["objectives_complete"] = True

    report = runtime.run_command(context.campaign_id, f"report {authored_offer['quest_id']}")
    assert report["command_type"] == "quest"
    assert authored_offer["quest_id"] in context.campaign_state.get("completed_quest_ids", [])

    runtime.save_campaign(context.campaign_id, "authored_town_loop_contract_slot", "AuthoredTownLoop")
    loaded = runtime.load_campaign("authored_town_loop_contract_slot")

    assert authored_offer["quest_id"] in loaded.campaign_state.get("completed_quest_ids", [])
    loaded_authored_offers = [offer for offer in current_quest_offers(loaded) if offer.get("source") == "authored_campaign"]
    assert loaded_authored_offers
    assert all(offer.get("source") == "authored_campaign" or offer.get("source") == "procedural_region" for offer in current_quest_offers(loaded))
