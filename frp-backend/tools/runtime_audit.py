"""Repo-wide runtime audit helpers for module mapping and structural checks."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_MAP_DOC = REPO_ROOT / "docs" / "runtime_module_map.md"
RUNTIME_ROOTS = [
    REPO_ROOT / "frp-backend" / "engine",
    REPO_ROOT / "frp-backend" / "tools",
    REPO_ROOT / "godot-client",
]
MAX_RUNTIME_LINES = 450
ALLOWED_OVERSIZE: Dict[str, str] = {
    "frp-backend/engine/world/inventory.py": "Pending split of inventory domain models from container logic.",
    "frp-backend/engine/world/interactions.py": "Pending split of interaction catalog from handlers.",
    "frp-backend/engine/core/combat.py": "Combat core remains monolithic until rules/narration are peeled apart.",
    "frp-backend/engine/core/dm_agent.py": "DM agent still mixes prompting, fallback, and formatting.",
    "frp-backend/engine/map/__init__.py": "Map generation package still centralizes multiple generators.",
    "frp-backend/engine/world/institutions.py": "Institution simulation remains unsplit.",
    "frp-backend/engine/data_loader.py": "Pure data loader exception.",
    "frp-backend/tools/play_topdown.py": "Terminal renderer surface exception.",
    "frp-backend/tools/play.py": "CLI surface exception.",
}
FORBIDDEN_SNIPPETS: Dict[str, List[str]] = {
    "frp-backend/engine/world/consequence.py": [
        "merchant_killed_price_rise",
        "helped_merchant_discount",
        "steal_detected_guards",
    ],
    "frp-backend/engine/campaign/__init__.py": [
        "Goblin Problem",
        "Roadside Ambush",
        "Dark Forest",
    ],
    "frp-backend/engine/world/history.py": [
        "War of the Broken Crown",
        "Kingdom of Valdris",
        "harbor_guard",
    ],
    "frp-backend/engine/llm/__init__.py": [
        "/home/msbel/",
        "https://api.githubcopilot.com",
    ],
    "godot-client/autoloads/backend.gd": [
        "192.168.1.55",
    ],
    "godot-client/scenes/title_screen.gd": [
        "class_option.add_item(\"Warrior\")",
        "class_option.add_item(\"Rogue\")",
        "class_option.add_item(\"Mage\")",
        "class_option.add_item(\"Priest\")",
    ],
}


def _iter_runtime_files() -> Iterable[Path]:
    for root in RUNTIME_ROOTS:
        if not root.exists():
            continue
        pattern = "*.gd" if root.name == "godot-client" else "*.py"
        for path in root.rglob(pattern):
            if "__pycache__" in path.parts or "saves" in path.parts or ".pytest_cache" in path.parts:
                continue
            yield path


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _python_map(path: Path, lines: List[str]) -> Dict[str, Any]:
    tree = ast.parse("\n".join(lines))
    classes = []
    functions = []
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
    return {"classes": classes, "functions": functions, "imports": sorted(set(imports))}


def _gdscript_map(lines: List[str]) -> Dict[str, Any]:
    functions = []
    classes = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("class_name "):
            classes.append({"name": stripped.split(" ", 1)[1], "methods": []})
        if stripped.startswith("func "):
            functions.append(stripped.split("(", 1)[0].replace("func ", ""))
    return {"classes": classes, "functions": functions, "imports": []}


def build_runtime_module_map() -> List[Dict[str, Any]]:
    result = []
    for path in sorted(_iter_runtime_files()):
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        entry = {
            "path": _relative(path),
            "lines": len(lines),
            "language": path.suffix.lstrip("."),
        }
        if path.suffix == ".py":
            entry.update(_python_map(path, lines))
        else:
            entry.update(_gdscript_map(lines))
        result.append(entry)
    return result


def render_runtime_module_map() -> str:
    lines = [
        "| Path | Lines | Classes | Functions |",
        "|---|---:|---|---|",
    ]
    for entry in build_runtime_module_map():
        class_summary = ", ".join(
            f"{item['name']} ({len(item['methods'])})" for item in entry["classes"][:4]
        ) or "-"
        function_summary = ", ".join(entry["functions"][:4]) or "-"
        lines.append(
            f"| `{entry['path']}` | {entry['lines']} | {class_summary} | {function_summary} |"
        )
    return "\n".join(lines)


def render_runtime_module_map_document() -> str:
    lines = [
        "# Runtime Module Map",
        "",
        "Generated by `python -m tools.runtime_audit`.",
        "",
        "Oversized runtime files are only permitted when explicitly documented below.",
        "",
        "## Oversize Exceptions",
        "",
    ]
    for path, reason in sorted(ALLOWED_OVERSIZE.items()):
        lines.append(f"- `{path}`: {reason}")
    lines.extend(
        [
            "",
            "## Module Map",
            "",
            render_runtime_module_map(),
        ]
    )
    return "\n".join(lines)


def module_map_is_fresh() -> bool:
    if not MODULE_MAP_DOC.exists():
        return False
    current = render_runtime_module_map_document().strip()
    recorded = MODULE_MAP_DOC.read_text(encoding="utf-8").strip()
    return current == recorded


def find_audit_violations() -> List[str]:
    violations: List[str] = []
    if not module_map_is_fresh():
        violations.append("runtime module map is stale: docs/runtime_module_map.md")
    for path in sorted(_iter_runtime_files()):
        rel = _relative(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        if len(lines) > MAX_RUNTIME_LINES and rel not in ALLOWED_OVERSIZE:
            violations.append(f"oversize runtime file without exception: {rel} ({len(lines)} lines)")
        for snippet in FORBIDDEN_SNIPPETS.get(rel, []):
            if snippet in text:
                violations.append(f"forbidden inline runtime data in {rel}: {snippet}")
    return violations


if __name__ == "__main__":
    print(render_runtime_module_map_document())
    violations = find_audit_violations()
    if violations:
        print("\n## Violations")
        for violation in violations:
            print(f"- {violation}")
