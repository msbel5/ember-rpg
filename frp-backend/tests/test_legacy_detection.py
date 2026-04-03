"""Phase 7: Legacy code detection tests.

Tracks the reduction of legacy engine.core imports across the codebase.
These tests document the current state and fail if legacy usage increases.
"""

import pathlib
import re

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent

# Files confirmed dead and deleted in Phase 7.
# enemy_ai.py kept because combat.py still imports it in the session chain.
DELETED_DEAD_FILES = {
    "engine/core/campaign.py",
    "engine/core/loot.py",
    "engine/core/monster.py",
    "engine/core/npc.py",
    "engine/core/rules.py",
}


def _count_legacy_imports(directory: str = "engine") -> dict[str, int]:
    """Count 'from engine.core.*' imports per source file."""
    results: dict[str, int] = {}
    target = BACKEND_DIR / directory
    for py_file in sorted(target.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = str(py_file.relative_to(BACKEND_DIR))
        # Skip files inside engine/core itself.
        if rel.startswith("engine/core"):
            continue
        count = 0
        for line in py_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if re.match(r"^\s*from engine\.core\.", line):
                count += 1
        if count > 0:
            results[rel] = count
    return results


def test_dead_files_are_deleted():
    """Confirmed dead engine/core files must not exist."""
    for rel_path in DELETED_DEAD_FILES:
        full = BACKEND_DIR / rel_path
        assert not full.exists(), f"Dead file still exists: {rel_path}"


def test_legacy_import_count_does_not_increase():
    """Total engine.core imports outside core must not increase.

    Current baseline: ~40 imports across ~15 files.
    This ceiling prevents new legacy dependencies from being added.
    """
    imports = _count_legacy_imports()
    total = sum(imports.values())
    # Set ceiling at current level + small margin.
    # As handlers are rewritten, this number should decrease.
    MAX_ALLOWED = 60
    assert total <= MAX_ALLOWED, (
        f"Legacy import count ({total}) exceeds ceiling ({MAX_ALLOWED}).\n"
        f"Files with imports:\n"
        + "\n".join(f"  {f}: {c}" for f, c in sorted(imports.items()))
    )


def test_no_new_kernel_files_import_core():
    """No file in engine/kernel/ should import from engine.core."""
    kernel_dir = BACKEND_DIR / "engine" / "kernel"
    violations = []
    for py_file in sorted(kernel_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*from engine\.core\.", line):
                violations.append(f"{py_file.name}:{lineno}")
    assert violations == [], (
        "Kernel files must not import engine.core:\n" + "\n".join(violations)
    )


def test_kernel_adapter_has_no_core_imports():
    """kernel_adapter.py must have no 'from engine.core' import statements."""
    adapter = BACKEND_DIR / "engine" / "api" / "kernel_adapter.py"
    for lineno, line in enumerate(adapter.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("from engine.core"):
            raise AssertionError(f"kernel_adapter.py:{lineno} imports engine.core: {stripped}")
