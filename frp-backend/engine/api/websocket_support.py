"""Helpers for detecting whether the runtime can actually serve WebSockets."""
from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec


@lru_cache(maxsize=1)
def websocket_support_payload() -> dict[str, object]:
    for library in ("websockets", "wsproto"):
        if find_spec(library) is not None:
            return {
                "websocket_transport": True,
                "websocket_library": library,
            }
    return {
        "websocket_transport": False,
        "websocket_library": "",
    }


def websocket_transport_available() -> bool:
    return bool(websocket_support_payload()["websocket_transport"])


__all__ = ["websocket_support_payload", "websocket_transport_available"]
