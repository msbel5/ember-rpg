"""Verify that no legacy session-first imports remain in the codebase."""
from __future__ import annotations

import os
import re

import pytest

BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..")
LEGACY_PATTERNS = [
    r"from engine\.api\.routes import",
    r"from engine\.api\.models import",
    r"from engine\.api\.shop_routes import",
    r"from engine\.api\.inventory_routes import",
    r"from engine\.api\.save_routes import",
    r"from engine\.api\.npc_memory_routes import",
    r"from engine\.api\.scene_routes import",
    r"from engine\.world\.world_routes import",
    r"from engine\.api\.game_session import",
    r"import engine\.api\.game_session\b",
    r"from engine\.api\.save_system import",
    r"import engine\.api\.save_system\b",
    r"from engine\.api\.handlers\.combat_handlers import",
    r"import engine\.api\.handlers\.combat_handlers\b",
    r"from engine\.api\.handlers\.exploration_handlers import",
    r"import engine\.api\.handlers\.exploration_handlers\b",
    r"from engine\.api\.handlers\.helpers import",
    r"import engine\.api\.handlers\.helpers\b",
    r"from engine\.api\.handlers\.inventory_handlers import",
    r"import engine\.api\.handlers\.inventory_handlers\b",
    r"from engine\.api\.handlers\.social_handlers import",
    r"import engine\.api\.handlers\.social_handlers\b",
    r"from engine\.kernel\.scene_types import DMContext\b",
]


def _scan_for_legacy_imports():
    """Scan all Python files for legacy imports."""
    hits = []
    for root, _, files in os.walk(BACKEND_ROOT):
        if ".git" in root or "__pycache__" in root:
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    for pattern in LEGACY_PATTERNS:
                        if re.search(pattern, line):
                            hits.append(f"{filepath}:{line_num}: {line.strip()}")
    return hits


class TestNoLegacyImports:
    def test_no_legacy_route_imports(self):
        hits = _scan_for_legacy_imports()
        assert hits == [], f"Legacy imports found:\n" + "\n".join(hits)

    def test_legacy_files_deleted(self):
        legacy_files = [
            "engine/api/routes.py",
            "engine/api/models.py",
            "engine/api/shop_routes.py",
            "engine/api/inventory_routes.py",
            "engine/api/save_routes.py",
            "engine/api/npc_memory_routes.py",
            "engine/api/scene_routes.py",
            "engine/world/world_routes.py",
            "engine/api/game_session.py",
            "engine/api/save_system.py",
            "engine/api/handlers/combat_handlers.py",
            "engine/api/handlers/exploration_handlers.py",
            "engine/api/handlers/helpers.py",
            "engine/api/handlers/inventory_handlers.py",
            "engine/api/handlers/social_handlers.py",
        ]
        for f in legacy_files:
            full = os.path.join(BACKEND_ROOT, f)
            assert not os.path.exists(full), f"Legacy file still exists: {f}"
