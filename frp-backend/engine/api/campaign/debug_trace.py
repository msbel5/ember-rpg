"""Structured debug tracing for campaign runtime cutover."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any


logger = logging.getLogger("ember.campaign")


def snapshot_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def trace_event(event: str, **fields: Any) -> None:
    record = {"event": event, **fields}
    logger.debug(json.dumps(record, sort_keys=True, default=str))


__all__ = ["snapshot_hash", "trace_event"]
