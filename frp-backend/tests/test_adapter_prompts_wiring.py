from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import asset_pipeline as ap


def _sample_item() -> dict:
    return {
        "id": "laser_rifle",
        "name": "Laser Rifle",
        "type": "weapon",
        "rarity": "RARE",
        "description": "A modular frontier energy rifle.",
        "damage_type": "energy",
    }


def test_adapter_applies_prefix_and_seed_offset() -> None:
    adapter = ap.resolve_adapter("scifi_frontier")
    adapter["id"] = "scifi_frontier"

    with (
        patch.object(ap, "load_json", return_value={"items": [_sample_item()]}),
        patch.object(ap, "build_item_prompt", return_value="PROMPT") as build_prompt,
        patch.object(ap, "stable_seed", return_value=1337),
    ):
        jobs = ap.build_item_jobs(limit=1, adapter=adapter)

    assert len(jobs) == 1
    assert jobs[0].seed == 2337
    assert jobs[0].metadata["adapter_id"] == "scifi_frontier"
    style_prefix = build_prompt.call_args.kwargs["style_prefix"]
    assert style_prefix.startswith(adapter["prompt_prefix"])
    assert ap.ITEM_STYLE_PREFIX in style_prefix


def test_adapter_none_preserves_default() -> None:
    with (
        patch.object(ap, "load_json", return_value={"items": [_sample_item()]}),
        patch.object(ap, "build_item_prompt", return_value="PROMPT") as build_prompt,
        patch.object(ap, "stable_seed", return_value=1337),
    ):
        jobs = ap.build_item_jobs(limit=1, adapter={})

    assert len(jobs) == 1
    assert jobs[0].seed == 1337
    assert jobs[0].metadata["adapter_id"] == ""
    assert build_prompt.call_args.kwargs["style_prefix"] == ap.ITEM_STYLE_PREFIX
