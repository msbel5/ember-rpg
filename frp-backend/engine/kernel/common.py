from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def serialize_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: serialize_value(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(val) for key, val in value.items()}
    return value
