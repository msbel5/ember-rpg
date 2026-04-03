from __future__ import annotations

import json
from pathlib import Path

from tools.content_orchestrator import prepare_packets
from tools.content_validator import run_dry_run, validate_batches


def _manifest(work_root: Path) -> dict:
    return json.loads((work_root / "tmp" / "content_packets" / "manifest.json").read_text(encoding="utf-8"))


def _family_entry(work_root: Path, family: str) -> dict:
    manifest = _manifest(work_root)
    return next(entry for entry in manifest["families"] if entry["name"] == family)


def test_prepare_packets_writes_packets_prompts_and_manifest(tmp_path: Path):
    manifest = prepare_packets(batch_id="20260403_120000", work_root=tmp_path)

    packets_dir = tmp_path / "tmp" / "content_packets"
    assert manifest["batch_id"] == "20260403_120000"
    assert (packets_dir / "copilot_master_prompt.txt").exists()
    assert (packets_dir / "manifest.json").exists()
    assert len(manifest["families"]) == 32  # All generatable families
    assert len(manifest["review_assignments"]) == 32

    for family in (
        "npc_templates",
        "items_equipment",
        "items_supplies",
        "recipes",
        "spells",
        "worldgen",
        "campaign_history_social",
    ):
        assert (packets_dir / f"{family}.json").exists()
        assert (packets_dir / f"{family}.md").exists()
        assert (packets_dir / f"{family}_creator_prompt.txt").exists()
        assert (packets_dir / f"{family}_reviewer_prompt.txt").exists()


def test_validate_batches_fails_when_candidates_are_missing(tmp_path: Path):
    prepare_packets(batch_id="20260403_120000", work_root=tmp_path)

    result = validate_batches(batch_id="20260403_120000", work_root=tmp_path, strict_missing=True)

    assert result["overall_status"] == "fail"
    assert all(entry["status"] == "missing" for entry in result["families"])
    summary = (tmp_path / "reports" / "content_validation_summary.md").read_text(encoding="utf-8")
    assert "candidate file missing" in summary
    assert "`npc_templates`" in summary


def test_validate_batches_accepts_valid_recipe_candidate(tmp_path: Path):
    prepare_packets(batch_id="20260403_120000", work_root=tmp_path)
    entry = _family_entry(tmp_path, "recipes")
    Path(entry["candidate"]).parent.mkdir(parents=True, exist_ok=True)
    Path(entry["review"]).parent.mkdir(parents=True, exist_ok=True)
    Path(entry["candidate"]).write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "iron_bar_refine_bundle",
                        "name": "Refined Iron Bar Bundle",
                        "workstation": "forge",
                        "skill": "smithing",
                        "skill_dc": 12,
                        "ap_cost": 6,
                        "ingredients": [
                            {"item_id": "iron_ore", "quantity": 3, "material_class": None},
                            {"item_id": "coal", "quantity": 1, "material_class": None},
                        ],
                        "products": [
                            {"item_id": "iron_bar", "quantity": 2, "inherit_material": False},
                        ],
                        "tools": ["hammer", "tongs"],
                        "failure_result": "slag",
                        "xp_reward": 10,
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    Path(entry["review"]).write_text("# pass\n", encoding="utf-8")

    result = validate_batches(batch_id="20260403_120000", work_root=tmp_path, strict_missing=False)
    recipe_result = next(item for item in result["families"] if item["name"] == "recipes")

    assert recipe_result["status"] == "pass"
    assert not recipe_result["errors"]
    assert result["overall_status"] == "pass_with_warnings"


def test_validate_batches_rejects_invalid_npc_candidate(tmp_path: Path):
    prepare_packets(batch_id="20260403_120000", work_root=tmp_path)
    entry = _family_entry(tmp_path, "npc_templates")
    Path(entry["candidate"]).parent.mkdir(parents=True, exist_ok=True)
    Path(entry["review"]).parent.mkdir(parents=True, exist_ok=True)
    Path(entry["candidate"]).write_text(
        json.dumps(
            {
                "npc_templates": [
                    {
                        "id": "market_runner_01",
                        "name": "Darin Quickstep",
                        "role": "merchant",
                        "personality": ["nervous", "clever"],
                        "speech_style": "casual",
                        "dialogue": {
                            "greeting": ["Need something moved?"],
                            "farewell": ["Keep your hood up."],
                            "quest_offer": ["I lost a package near the east gate."],
                            "quest_complete": ["You found it. Good."],
                            "combat_warning": ["Not here, not now!"],
                            "idle": ["The watch asks too many questions."],
                        },
                        "disposition": "friendly",
                        "faction": "shadow_broker_ring",
                        "level_range": [1, 3],
                        "shop_inventory": ["nonexistent_knife"],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    Path(entry["review"]).write_text("# fail\n", encoding="utf-8")

    result = validate_batches(batch_id="20260403_120000", work_root=tmp_path, strict_missing=False)
    npc_result = next(item for item in result["families"] if item["name"] == "npc_templates")

    assert npc_result["status"] == "fail"
    assert any("unknown item" in error for error in npc_result["errors"])
    assert any("unknown faction" in error for error in npc_result["errors"])


def test_dry_run_writes_summary_and_prompt_artifacts(tmp_path: Path):
    result = run_dry_run(batch_id="20260403_120000", work_root=tmp_path)

    assert result["batch_id"] == "20260403_120000"
    assert result["overall_status"] == "pass_with_warnings"
    assert (tmp_path / "reports" / "content_validation_summary.md").exists()
    summary = (tmp_path / "reports" / "content_validation_summary.md").read_text(encoding="utf-8")
    assert "Overall status" in summary
    assert "`worldgen`" in summary
    assert "candidate file missing" in summary
