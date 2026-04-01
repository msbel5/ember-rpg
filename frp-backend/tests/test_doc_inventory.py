from pathlib import Path

from tools.doc_inventory import (
    ACTIVE_PRD_DIR,
    MATRIX_DOC,
    find_doc_inventory_violations,
    render_doc_inventory_document,
)


def test_active_prds_live_under_active_directory():
    active_paths = sorted(ACTIVE_PRD_DIR.glob("PRD_*.md"))
    assert active_paths
    assert all(path.parent == ACTIVE_PRD_DIR for path in active_paths)


def test_doc_inventory_has_no_governance_violations():
    assert not find_doc_inventory_violations()


def test_generated_matrix_matches_rendered_inventory():
    assert MATRIX_DOC.read_text(encoding="utf-8").strip() == render_doc_inventory_document().strip()


def test_mechanics_canon_exists():
    canon_path = Path(__file__).resolve().parents[2] / "docs" / "architecture" / "ember_mechanics_canon_v1.md"
    assert canon_path.exists()
