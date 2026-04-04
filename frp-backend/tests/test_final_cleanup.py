"""Final cleanup verification tests.

These tests enforce that ALL legacy engine.core references have been
removed from the entire codebase -- kernel, tests, tools, and data files.
"""

import ast
import pathlib
import re

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent


# ── 1. Zero engine.core imports across entire codebase ──────────────


def _find_core_imports(directory: str) -> dict[str, list[int]]:
    """Find all 'from engine.core' import lines in a directory tree.

    Returns {relative_path: [line_numbers]} for every file that has
    at least one engine.core import.  Skips __pycache__ and this test
    file itself (which contains the pattern as a search string).
    """
    results: dict[str, list[int]] = {}
    target = BACKEND_DIR / directory
    if not target.exists():
        return results
    for py_file in sorted(target.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = str(py_file.relative_to(BACKEND_DIR))
        # Skip guardrail test files that contain pattern strings.
        if rel.endswith("test_legacy_detection.py"):
            continue
        if rel.endswith("test_kernel_adapter.py"):
            continue
        if rel.endswith("test_final_cleanup.py"):
            continue
        lines = []
        for lineno, line in enumerate(
            py_file.read_text(encoding="utf-8", errors="ignore").splitlines(),
            start=1,
        ):
            stripped = line.strip()
            if re.match(r"^from engine\.core[\.\s]", stripped):
                lines.append(lineno)
            elif re.match(r"^import engine\.core", stripped):
                lines.append(lineno)
        if lines:
            results[rel] = lines
    return results


def test_zero_core_imports_in_engine():
    """No file in engine/ should import from engine.core."""
    violations = _find_core_imports("engine")
    assert violations == {}, (
        "engine/ still has engine.core imports:\n"
        + "\n".join(f"  {f}:{lines}" for f, lines in sorted(violations.items()))
    )


def test_zero_core_imports_in_tests():
    """No test file should import from engine.core."""
    violations = _find_core_imports("tests")
    assert violations == {}, (
        "tests/ still has engine.core imports:\n"
        + "\n".join(f"  {f}:{lines}" for f, lines in sorted(violations.items()))
    )


def test_zero_core_imports_in_tools():
    """No tools/ file should import from engine.core."""
    violations = _find_core_imports("tools")
    assert violations == {}, (
        "tools/ still has engine.core imports:\n"
        + "\n".join(f"  {f}:{lines}" for f, lines in sorted(violations.items()))
    )


# ── 2. No D&D stat fallback chains in kernel ────────────────────────


_DND_STAT_NAMES = {
    "STR", "DEX", "CON", "INT", "WIS", "CHA",
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
    "agility",  # lowercase non-canonical
}


def test_no_dnd_stat_fallbacks_in_combat_wounds():
    """combat_wounds.py must not fallback to D&D or lowercase stat names."""
    path = BACKEND_DIR / "engine" / "kernel" / "combat_wounds.py"
    source = path.read_text(encoding="utf-8")
    for name in _DND_STAT_NAMES:
        assert f'"{name}"' not in source, (
            f"combat_wounds.py still references D&D stat name '{name}'"
        )


def test_no_dnd_stat_fallbacks_in_syndromes():
    """systems_syndromes.py must not fallback to uppercase TOUGHNESS or DISEASE_RESISTANCE."""
    path = BACKEND_DIR / "engine" / "kernel" / "systems_syndromes.py"
    source = path.read_text(encoding="utf-8")
    assert '"TOUGHNESS"' not in source, "systems_syndromes.py still uses TOUGHNESS"
    assert '"DISEASE_RESISTANCE"' not in source, "systems_syndromes.py still uses DISEASE_RESISTANCE"


# ── 3. No hardcoded quality multipliers in kernel ────────────────────


def test_no_hardcoded_quality_multipliers():
    """combat_types.py must load quality tiers from data_loader, not hardcode them."""
    path = BACKEND_DIR / "engine" / "kernel" / "combat_types.py"
    source = path.read_text(encoding="utf-8")
    # The hardcoded dict should be gone.
    assert "QUALITY_MULTIPLIERS = {" not in source, (
        "combat_types.py still has hardcoded QUALITY_MULTIPLIERS dict"
    )


def test_quality_tiers_loaded_from_json():
    """QUALITY_MULTIPLIERS must come from data_loader.load_quality_tiers()."""
    from engine.kernel.combat_types import QUALITY_MULTIPLIERS
    from engine.kernel.data_loader import load_quality_tiers

    json_tiers = load_quality_tiers()
    assert QUALITY_MULTIPLIERS == json_tiers, (
        f"QUALITY_MULTIPLIERS mismatch: code={QUALITY_MULTIPLIERS}, json={json_tiers}"
    )


# ── 4. effects.py alias map is minimal ──────────────────────────────


def test_effects_stat_lookup_no_dnd_vocabulary():
    """_stat_lookup aliases must not contain D&D stat vocabulary."""
    path = BACKEND_DIR / "engine" / "kernel" / "effects.py"
    source = path.read_text(encoding="utf-8")
    dnd_words = ["constitution", "dexterity", "wisdom", "strength", "intelligence", "charisma"]
    for word in dnd_words:
        assert f'"{word}"' not in source, (
            f"effects.py still contains D&D alias '{word}'"
        )


# ── 5. tools/ files use kernel imports ───────────────────────────────


def test_tools_campaign_client_imports_kernel():
    """campaign_client.py must import from engine.kernel.creation, not engine.core."""
    path = BACKEND_DIR / "tools" / "campaign_client.py"
    source = path.read_text(encoding="utf-8")
    assert "engine.core" not in source, "campaign_client.py still imports engine.core"
    assert "engine.kernel.creation" in source, "campaign_client.py must use engine.kernel.creation"


def test_tools_play_topdown_deleted():
    """play_topdown.py was removed in campaign-first migration."""
    path = BACKEND_DIR / "tools" / "play_topdown.py"
    assert not path.exists(), f"Stale tool should be deleted: {path}"


def test_tools_play_topdown_view_deleted():
    """play_topdown_view.py was removed in campaign-first migration."""
    path = BACKEND_DIR / "tools" / "play_topdown_view.py"
    assert not path.exists(), f"Stale tool should be deleted: {path}"
