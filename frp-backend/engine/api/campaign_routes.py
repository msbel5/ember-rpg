"""Campaign-first API routes backed by engine.worldgen."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from engine.api.campaign_models import (
    CampaignCommandRequest,
    CampaignCommandResponse,
    CampaignSaveRequest,
    CampaignSaveResponse,
    CampaignSaveSummary,
    CampaignSnapshotResponse,
    CreateCampaignRequest,
)
from engine.api.campaign_runtime import CampaignRuntime


router = APIRouter()


def _make_llm_callable():
    from engine.llm import build_game_narrator

    return build_game_narrator()


campaign_runtime = CampaignRuntime(llm=_make_llm_callable())


@router.post("/campaigns", response_model=CampaignSnapshotResponse)
def create_campaign(req: CreateCampaignRequest):
    context = campaign_runtime.create_campaign(
        player_name=req.player_name,
        player_class=req.player_class,
        adapter_id=req.adapter_id,
        profile_id=req.profile_id,
        seed=req.seed,
    )
    return campaign_runtime.snapshot(
        context.campaign_id,
        narrative=context.recent_event_log[0]["summary"] if context.recent_event_log else "",
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignSnapshotResponse)
def get_campaign(campaign_id: str):
    try:
        return campaign_runtime.snapshot(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc


@router.post("/campaigns/{campaign_id}/commands", response_model=CampaignCommandResponse)
def run_campaign_command(campaign_id: str, req: CampaignCommandRequest):
    try:
        return campaign_runtime.run_command(campaign_id, req.input, req.shortcut, req.args)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/region/current")
def get_current_region(campaign_id: str):
    try:
        return campaign_runtime.get_current_region(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc


@router.get("/campaigns/{campaign_id}/settlement/current")
def get_current_settlement(campaign_id: str):
    try:
        return campaign_runtime.get_current_settlement(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc


@router.post("/campaigns/{campaign_id}/save", response_model=CampaignSaveResponse)
def save_campaign(campaign_id: str, req: CampaignSaveRequest):
    try:
        metadata = campaign_runtime.save_campaign(campaign_id, req.slot_name, req.player_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc
    return CampaignSaveResponse(
        save_id=str(metadata.get("slot_name", "")),
        slot_name=str(metadata.get("slot_name", "")),
        timestamp=str(metadata.get("timestamp", "")),
        schema_version=str(metadata.get("schema_version", "")),
    )


@router.get("/campaigns/{campaign_id}/saves", response_model=list[CampaignSaveSummary])
def list_campaign_saves(campaign_id: str):
    try:
        saves = campaign_runtime.list_campaign_saves(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc
    return [
        CampaignSaveSummary(
            save_id=str(entry.get("slot_name", "")),
            slot_name=str(entry.get("slot_name", "")),
            player_id=str(entry.get("player_name", "")),
            timestamp=str(entry.get("timestamp", "")),
            schema_version=str(entry.get("schema_version", "")),
            location=entry.get("location"),
            game_time=entry.get("game_time"),
        )
        for entry in saves
    ]


@router.post("/campaigns/load/{save_id}", response_model=CampaignSnapshotResponse)
def load_campaign(save_id: str):
    try:
        context = campaign_runtime.load_campaign(save_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return campaign_runtime.snapshot(
        context.campaign_id,
        narrative=f"Loaded campaign from {save_id}.",
    )


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    try:
        campaign_runtime.delete_campaign(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}") from exc
    return {"status": "deleted", "campaign_id": campaign_id}
