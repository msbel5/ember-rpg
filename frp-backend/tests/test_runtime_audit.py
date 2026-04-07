from tools.runtime_audit import (
    ALLOWED_OVERSIZE,
    MODULE_MAP_DOCS,
    build_runtime_module_map,
    find_audit_violations,
    render_runtime_module_map_document,
)


def test_runtime_module_map_covers_core_surfaces():
    module_map = build_runtime_module_map()
    by_path = {entry["path"]: entry for entry in module_map}

    assert "frp-backend/engine/api/campaign/context.py" in by_path
    assert "frp-backend/engine/api/save/core.py" in by_path
    assert "frp-backend/engine/api/context_factory.py" in by_path
    assert "frp-backend/engine/api/runtime_constants.py" in by_path
    assert "godot-client/autoloads/backend.gd" in by_path

    campaign_context = by_path["frp-backend/engine/api/campaign/context.py"]
    assert any(item["name"] == "CampaignContext" for item in campaign_context["classes"])

    save_core = by_path["frp-backend/engine/api/save/core.py"]
    assert any(item["name"] == "SaveSystem" for item in save_core["classes"])


def test_runtime_audit_has_no_unexpected_violations():
    assert not find_audit_violations()


def test_oversize_exceptions_are_explicitly_documented():
    assert "frp-backend/engine/api/campaign/live_kernel.py" in ALLOWED_OVERSIZE
    assert "frp-backend/engine/api/campaign/crime.py" in ALLOWED_OVERSIZE
    assert "frp-backend/engine/api/combat_bridge.py" in ALLOWED_OVERSIZE
    assert "godot-client/tests/automation/godot/automation_bridge.gd" in ALLOWED_OVERSIZE
    assert "godot-client/tests/run_headless_tests.gd" in ALLOWED_OVERSIZE


def test_runtime_module_map_document_matches_generated_output():
    expected = render_runtime_module_map_document().strip()
    for doc_path in MODULE_MAP_DOCS:
        assert doc_path.read_text(encoding="utf-8").strip() == expected
