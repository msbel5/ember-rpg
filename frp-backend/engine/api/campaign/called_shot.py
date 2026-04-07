"""Called-shot validation and payload helpers."""
from __future__ import annotations

from typing import Any


def _normalize_called_shot(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace(" ", "_")
    return text or None


def _called_shot_zones(actor: Any) -> list[str]:
    body_state = getattr(actor, "body_state", None)
    if body_state is None:
        return []
    plan = getattr(body_state, "plan", None)
    zones: list[str] = []
    for part in list(getattr(plan, "parts", []) or []):
        part_id = str(getattr(part, "part_id", "")).strip()
        if part_id and part_id not in zones:
            zones.append(part_id)
    if zones:
        return zones
    for part_id in list(getattr(body_state, "parts", {}).keys()):
        normalized = str(part_id).strip()
        if normalized and normalized not in zones:
            zones.append(normalized)
    return zones


def _validate_called_shot(target: Any, called_shot: str | None) -> str | None:
    if not called_shot:
        return None
    valid_zones = _called_shot_zones(target)
    if not valid_zones:
        return f"{target.identity.display_name} does not expose called shot zones."
    if called_shot in valid_zones:
        return None
    return f"Invalid called shot '{called_shot}'. Valid zones: {', '.join(valid_zones)}."


__all__ = ["_called_shot_zones", "_normalize_called_shot", "_validate_called_shot"]
