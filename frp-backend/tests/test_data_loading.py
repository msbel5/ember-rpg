"""Phase 6: Data externalization tests.

Verifies that all game constants load from JSON data files,
not hardcoded Python dicts.
"""

import pathlib

from engine.kernel.data_loader import (
    clear_cache,
    load_materials,
    load_quality_tiers,
)

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


def setup_function():
    """Clear cache before each test to ensure fresh loads."""
    clear_cache()


# ── Materials ────────────────────────────────────────────────────────

def test_all_materials_load_from_json():
    """Materials must load from data/materials.json."""
    materials = load_materials()
    assert len(materials) >= 10, f"Expected at least 10 materials, got {len(materials)}"
    assert "iron" in materials
    assert "steel" in materials
    assert "mithril" in materials
    iron = materials["iron"]
    assert iron.label == "Iron"
    assert iron.density == 1.0
    assert iron.impact_fracture > 0


def test_material_has_required_fields():
    """Each material must have all physical property fields."""
    materials = load_materials()
    for mat_id, mat in materials.items():
        assert mat.material_id, f"{mat_id} missing material_id"
        assert mat.label, f"{mat_id} missing label"
        assert mat.density > 0, f"{mat_id} has invalid density"
        assert mat.impact_yield > 0, f"{mat_id} has invalid impact_yield"
        assert mat.impact_fracture > mat.impact_yield, (
            f"{mat_id} fracture should exceed yield"
        )
        assert mat.max_edge > 0, f"{mat_id} has invalid max_edge"


# ── Quality tiers ────────────────────────────────────────────────────

def test_quality_tiers_load_from_json():
    """Quality tiers must load from data/quality_tiers.json."""
    tiers = load_quality_tiers()
    assert len(tiers) == 7, f"Expected 7 quality tiers, got {len(tiers)}"
    assert tiers[0] == 1.0  # Poor
    assert tiers[6] == 3.0  # Legendary


def test_quality_tiers_are_monotonic():
    """Quality multipliers must increase with tier."""
    tiers = load_quality_tiers()
    values = [tiers[i] for i in range(7)]
    for i in range(1, len(values)):
        assert values[i] >= values[i - 1], (
            f"Tier {i} ({values[i]}) should be >= tier {i-1} ({values[i-1]})"
        )


# ── Data files exist ─────────────────────────────────────────────────

def test_materials_json_exists():
    """data/materials.json must exist on disk."""
    assert (DATA_DIR / "materials.json").exists()


def test_quality_tiers_json_exists():
    """data/quality_tiers.json must exist on disk."""
    assert (DATA_DIR / "quality_tiers.json").exists()


# ── Missing file gives clear error ──────────────────────────────────

def test_missing_data_file_raises_clear_error():
    """Loading a nonexistent data file should raise FileNotFoundError."""
    from engine.kernel.data_loader import _load_json
    try:
        _load_json("nonexistent_file.json")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "data/*.json" in str(e) or "not found" in str(e).lower()
