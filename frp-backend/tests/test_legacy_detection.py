"""Phase 7: Legacy code detection tests.

Tracks the reduction of legacy engine.core imports across the codebase.
These tests document the current state and fail if legacy usage increases.
"""

import pathlib
import re

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent

# The entire engine/core/ directory has been deleted.
DELETED_CORE_DIR = "engine/core"


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


def test_core_directory_is_deleted():
    """The entire engine/core/ directory must not exist."""
    core_dir = BACKEND_DIR / DELETED_CORE_DIR
    assert not core_dir.exists(), f"Legacy directory still exists: {DELETED_CORE_DIR}"


def test_legacy_import_count_does_not_increase():
    """Total engine.core imports outside core must not increase.

    Current baseline: ~40 imports across ~15 files.
    This ceiling prevents new legacy dependencies from being added.
    """
    imports = _count_legacy_imports()
    total = sum(imports.values())
    # Set ceiling at current level + small margin.
    # As handlers are rewritten, this number should decrease.
    MAX_ALLOWED = 0  # engine/core/ is deleted -- no legacy imports allowed
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


def test_no_legacy_imports_in_tests():
    """No test file should import from engine.core (dead tests must be deleted)."""
    test_dir = BACKEND_DIR / "tests"
    violations = []
    skip = {"test_legacy_detection.py", "test_kernel_adapter.py", "test_final_cleanup.py"}
    for py_file in sorted(test_dir.rglob("*.py")):
        if "__pycache__" in str(py_file) or py_file.name in skip:
            continue
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.match(r"^\s*from engine\.core\.", line):
                violations.append(f"{py_file.name}:{lineno}")
    assert violations == [], (
        "Test files must not import engine.core:\n" + "\n".join(violations)
    )


def test_no_legacy_imports_in_tools():
    """No tools/ file should import from engine.core."""
    tools_dir = BACKEND_DIR / "tools"
    violations = []
    for py_file in sorted(tools_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.match(r"^\s*from engine\.core\.", line):
                violations.append(f"{py_file.name}:{lineno}")
    assert violations == [], (
        "Tools files must not import engine.core:\n" + "\n".join(violations)
    )
