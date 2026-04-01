"""Documentation inventory rendering and governance checks."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
ACTIVE_PRD_DIR = DOCS_ROOT / "prd" / "active"
DEPRECATED_PRD_DIR = DOCS_ROOT / "deprecated" / "prd"
DEPRECATED_NOTES_DIR = DOCS_ROOT / "deprecated" / "notes"
REGISTRY_PATH = DOCS_ROOT / "doc_registry.json"
MATRIX_DOC = DOCS_ROOT / "PRD_IMPLEMENTATION_MATRIX.md"
README_PATH = REPO_ROOT / "README.md"

ALLOWED_ROOT_PRDS = {"PRD_IMPLEMENTATION_MATRIX.md"}
STALE_ARTIFACTS = [
    REPO_ROOT / "frp-backend" / "tests" / "coverage.json",
    REPO_ROOT / "frp-backend" / ".coverage",
]
README_FORBIDDEN_PATTERNS = [
    r"\b53 PRDs\b",
    r"\b1700\+ tests\b",
    r"\b96% coverage\b",
    r"autoloads/backend\.gd line 5",
]


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _scan_active_prds() -> list[Path]:
    return sorted(ACTIVE_PRD_DIR.glob("PRD_*.md"))


def _scan_deprecated_prds() -> list[Path]:
    return sorted(DEPRECATED_PRD_DIR.glob("PRD_*.md"))


def _scan_deprecated_notes() -> list[Path]:
    return sorted(DEPRECATED_NOTES_DIR.glob("*.md"))


def _scan_disallowed_root_prds() -> list[Path]:
    return sorted(
        path for path in DOCS_ROOT.glob("PRD_*.md")
        if path.name not in ALLOWED_ROOT_PRDS
    )


def _scan_disallowed_root_notes() -> list[Path]:
    patterns = ("PROMPT_*.md", "GDD*.md")
    results: list[Path] = []
    for pattern in patterns:
        results.extend(sorted(DOCS_ROOT.glob(pattern)))
    return sorted(results)


def _title_for(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return path.stem


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def render_doc_inventory_document() -> str:
    registry = _load_registry()
    active_meta = registry.get("active_prds", {})
    active_prds = _scan_active_prds()
    deprecated_prds = _scan_deprecated_prds()
    deprecated_notes = _scan_deprecated_notes()

    lines = [
        "# PRD Implementation Matrix",
        "",
        "Generated from `docs/doc_registry.json` via `python -m tools.doc_inventory`.",
        "",
        "## Summary",
        "",
        f"- Active PRDs: {len(active_prds)}",
        f"- Deprecated PRDs: {len(deprecated_prds)}",
        f"- Deprecated Notes: {len(deprecated_notes)}",
        "- Canonical mechanics map: `docs/architecture/ember_mechanics_canon_v1.md`",
        "",
        "## Authoritative PRDs",
        "",
        "| Path | Owner | Mechanisms | Runtime Surface | Supersedes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for path in active_prds:
        meta = active_meta.get(path.name, {})
        runtime_surface = [f"`{surface}`" for surface in meta.get("runtime_surface", [])[:3]]
        supersedes = [f"`{surface}`" for surface in meta.get("supersedes", [])[:3]]
        lines.append(
            "| `{path}` | `{owner}` | {mechanics} | {runtime} | {supersedes} |".format(
                path=_relative(path),
                owner=meta.get("owner", "missing"),
                mechanics=_join(list(meta.get("mechanism_ids", []))),
                runtime=_join(runtime_surface),
                supersedes=_join(supersedes),
            )
        )

    lines.extend(
        [
            "",
            "## Deprecated PRDs",
            "",
        ]
    )
    for path in deprecated_prds:
        lines.append(f"- `{_relative(path)}`")

    lines.extend(
        [
            "",
            "## Deprecated Notes",
            "",
        ]
    )
    for path in deprecated_notes:
        lines.append(f"- `{_relative(path)}`")
    return "\n".join(lines)


def matrix_is_fresh() -> bool:
    if not MATRIX_DOC.exists():
        return False
    return MATRIX_DOC.read_text(encoding="utf-8").strip() == render_doc_inventory_document().strip()


def find_doc_inventory_violations() -> list[str]:
    registry = _load_registry()
    violations: list[str] = []
    active_meta = registry.get("active_prds", {})
    active_prds = _scan_active_prds()
    active_names = {path.name for path in active_prds}

    for path in _scan_disallowed_root_prds():
        violations.append(f"active PRD outside docs/prd/active: {_relative(path)}")
    for path in _scan_disallowed_root_notes():
        violations.append(f"deprecated note outside docs/deprecated/notes: {_relative(path)}")

    for path in active_prds:
        if path.name not in active_meta:
            violations.append(f"active PRD missing registry metadata: {_relative(path)}")
    for registered_name in sorted(active_meta):
        if registered_name not in active_names:
            violations.append(f"registry entry missing active PRD file: {registered_name}")

    for artifact in STALE_ARTIFACTS:
        if artifact.exists():
            violations.append(f"stale tracked artifact present: {_relative(artifact)}")

    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
        for pattern in README_FORBIDDEN_PATTERNS:
            if re.search(pattern, readme_text):
                violations.append(f"README contains drift-prone claim: {pattern}")

    if not matrix_is_fresh():
        violations.append("documentation inventory is stale: docs/PRD_IMPLEMENTATION_MATRIX.md")

    return violations


if __name__ == "__main__":
    print(render_doc_inventory_document())
    violations = find_doc_inventory_violations()
    if violations:
        print("\n## Violations")
        for violation in violations:
            print(f"- {violation}")
