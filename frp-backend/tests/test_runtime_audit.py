from tools.runtime_audit import (
    ALLOWED_OVERSIZE,
    build_runtime_module_map,
    find_audit_violations,
    render_runtime_module_map_document,
)


def test_runtime_module_map_covers_core_surfaces():
    module_map = build_runtime_module_map()
    by_path = {entry["path"]: entry for entry in module_map}

    assert "frp-backend/engine/api/campaign_session.py" in by_path
    assert "frp-backend/engine/api/save/core.py" in by_path
    assert "frp-backend/engine/api/session_factory.py" in by_path
    assert "frp-backend/engine/api/runtime_constants.py" in by_path
    assert "godot-client/autoloads/backend.gd" in by_path

    campaign_session = by_path["frp-backend/engine/api/campaign_session.py"]
    assert any(item["name"] == "CampaignSession" for item in campaign_session["classes"])

    save_core = by_path["frp-backend/engine/api/save/core.py"]
    assert any(item["name"] == "SaveSystem" for item in save_core["classes"])


def test_runtime_audit_has_no_unexpected_violations():
    assert not find_audit_violations()


def test_oversize_exceptions_are_explicitly_documented():
    assert "frp-backend/engine/core/combat.py" in ALLOWED_OVERSIZE
    assert "godot-client/tests/automation/godot/automation_bridge.gd" in ALLOWED_OVERSIZE
    assert "godot-client/tests/run_headless_tests.gd" in ALLOWED_OVERSIZE


def test_runtime_module_map_document_matches_generated_output():
    from pathlib import Path

    doc_path = Path(__file__).resolve().parents[2] / "docs" / "runtime_module_map.md"
    assert doc_path.read_text(encoding="utf-8").strip() == render_runtime_module_map_document().strip()
