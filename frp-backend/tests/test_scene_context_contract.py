from __future__ import annotations

from pathlib import Path

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel import scene_types
from engine.kernel.scene_types import SceneContext, SceneType


def test_scene_types_exports_neutral_context_only():
    assert hasattr(scene_types, "SceneContext")
    assert not hasattr(scene_types, "DMContext")
    assert not hasattr(scene_types, "NarratorService")
    assert not hasattr(scene_types, "DMAIAgent")


def test_scene_context_scene_type_name_round_trip():
    context = SceneContext(scene_type=SceneType.EXPLORATION, location="Harbor")

    assert context.scene_type_name == "exploration"

    context.scene_type_name = "combat"

    assert context.scene_type is SceneType.COMBAT
    assert context.scene_type_name == "combat"


def test_campaign_runtime_uses_scene_context():
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="SceneContract", seed=42)

    assert isinstance(context.dm_context, SceneContext)
    assert context.dm_context.scene_type is SceneType.EXPLORATION


def test_active_campaign_modules_no_longer_import_dmcontext():
    root = Path(__file__).resolve().parents[1]
    active_files = [
        root / "engine" / "api" / "context_factory.py",
        root / "engine" / "api" / "campaign" / "context.py",
        root / "engine" / "api" / "save" / "campaign_state_serializer.py",
    ]

    for path in active_files:
        text = path.read_text(encoding="utf-8")
        assert "DMContext" not in text, f"Found legacy DMContext import in {path.name}"
        assert "NarratorService" not in text, f"Found legacy NarratorService residue in {path.name}"
