from __future__ import annotations

import json
from pathlib import Path

from tools.content_orchestrator import FAMILY_ORDER, FAMILY_SPECS, FamilySpec, prepare_packets
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
    expected_families = [name for name in FAMILY_ORDER if FAMILY_SPECS[name].generatable]
    assert len(manifest["families"]) == len(expected_families)
    assert len(manifest["review_assignments"]) == len(expected_families)
    assert "world_quests" not in {entry["name"] for entry in manifest["families"]}

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


def test_validate_batches_treats_missing_sidecars_as_warnings_when_sources_exist(tmp_path: Path):
    prepare_packets(batch_id="20260403_120000", work_root=tmp_path)

    result = validate_batches(batch_id="20260403_120000", work_root=tmp_path, strict_missing=True)

    assert result["overall_status"] == "pass_with_warnings"
    assert all(entry["status"] == "pass" for entry in result["families"])
    summary = (tmp_path / "reports" / "content_validation_summary.md").read_text(encoding="utf-8")
    assert "workflow candidate file missing" in summary
    assert "`npc_templates`" in summary
    assert "| `npc_templates` | `pass` |" in summary


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


def test_validate_batches_fails_truthfully_when_runtime_source_is_absent(tmp_path: Path, monkeypatch):
    prepare_packets(batch_id="20260403_120000", work_root=tmp_path)
    manifest_path = tmp_path / "tmp" / "content_packets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monkeypatch.setitem(
        FAMILY_SPECS,
        "missing_source_probe",
        FamilySpec(
            name="missing_source_probe",
            source_files=("missing/probe.json",),
            collection_keys=("probe",),
            goal="Probe missing source handling.",
            constraints=(),
            consumers=(),
        ),
    )
    manifest["families"].append(
        {
            "name": "missing_source_probe",
            "candidate": str(tmp_path / "candidates" / "missing_source_probe" / "batch_20260403_120000.json"),
            "review": str(tmp_path / "reviews" / "missing_source_probe" / "batch_20260403_120000.md"),
            "packet_json": str(tmp_path / "tmp" / "content_packets" / "missing_source_probe.json"),
            "packet_md": str(tmp_path / "tmp" / "content_packets" / "missing_source_probe.md"),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = validate_batches(batch_id="20260403_120000", work_root=tmp_path, strict_missing=True)

    missing_source = next(entry for entry in result["families"] if entry["name"] == "missing_source_probe")
    assert result["overall_status"] == "fail"
    assert missing_source["status"] == "missing"
    assert any("source file missing" in error for error in missing_source["errors"])


def test_dry_run_writes_summary_and_prompt_artifacts(tmp_path: Path):
    result = run_dry_run(batch_id="20260403_120000", work_root=tmp_path)

    assert result["batch_id"] == "20260403_120000"
    assert result["overall_status"] == "pass_with_warnings"
    assert (tmp_path / "reports" / "content_validation_summary.md").exists()
    summary = (tmp_path / "reports" / "content_validation_summary.md").read_text(encoding="utf-8")
    assert "Overall status" in summary
    assert "`worldgen`" in summary
    assert "workflow candidate file missing" in summary
