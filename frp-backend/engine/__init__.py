"""Ember RPG core package.

Keep subpackages lazily addressable via ``engine.<name>`` so tests and tools can
patch concrete providers without forcing heavy imports during package import.
"""
from __future__ import annotations

from importlib import import_module
from types import ModuleType

__all__ = ["llm", "orchestrator"]


def __getattr__(name: str) -> ModuleType:
    if name in {"llm", "orchestrator"}:
        return import_module(f"engine.{name}")
    raise AttributeError(f"module 'engine' has no attribute {name!r}")
