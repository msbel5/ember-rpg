from __future__ import annotations

import hashlib
from typing import Any


def saved_or(payload: Any, cls: type, fallback):
    if payload is None:
        return fallback()
    if isinstance(payload, cls):
        return payload
    if hasattr(cls, "from_dict"):
        return cls.from_dict(dict(payload))
    return fallback()


def saved_list_or(payload: Any, cls: type, fallback):
    if not isinstance(payload, list):
        return fallback()
    return [item if isinstance(item, cls) else cls.from_dict(dict(item)) for item in payload]


def stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def active_site_id(context) -> str:
    return str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or context.region_snapshot.region_id
    )


__all__ = ["active_site_id", "saved_list_or", "saved_or", "stable_seed"]
