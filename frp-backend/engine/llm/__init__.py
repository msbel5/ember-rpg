"""Public LLM package surface.

Keep import-time side effects minimal so tests and campaign-first code can patch
provider entrypoints without requiring optional OpenAI dependencies.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable, Any

from .auth import CopilotAuthError, TokenResolution, resolve_copilot_token
from .cli_provider import CopilotCLIError, complete_with_copilot_cli
from .settings import (
    DEFAULT_NARRATION_MODE,
    DEFAULT_FAST_MODEL,
    DEFAULT_LIVE_MODEL,
    NARRATION_MODES,
    get_fallback_model_name,
    get_fast_model_name,
    get_live_model_name,
    get_narration_mode,
    get_runtime_settings,
    get_smart_model_name,
)

if TYPE_CHECKING:
    from .router import LLMRouter, LiveNarrationRequiredError


_SETTINGS = get_runtime_settings()

MODEL_LIVE = _SETTINGS.live_model
MODEL_FAST = _SETTINGS.fast_model
MODEL_SMART = _SETTINGS.smart_model
MODEL_FALLBACK = _SETTINGS.fallback_model
NARRATION_MODE_DEFAULT = _SETTINGS.narration_mode


def get_llm_router():
    from .router import get_llm_router as _get_llm_router

    return _get_llm_router()


def build_game_narrator() -> Callable[[str], Optional[str]]:
    from .builders import build_game_narrator as _build_game_narrator

    return _build_game_narrator()


def __getattr__(name: str) -> Any:
    if name in {"LLMRouter", "LiveNarrationRequiredError"}:
        from . import router as _router

        return getattr(_router, name)
    raise AttributeError(f"module 'engine.llm' has no attribute {name!r}")


__all__ = [
    "CopilotAuthError",
    "CopilotCLIError",
    "DEFAULT_FAST_MODEL",
    "DEFAULT_LIVE_MODEL",
    "DEFAULT_NARRATION_MODE",
    "LLMRouter",
    "LiveNarrationRequiredError",
    "MODEL_FAST",
    "MODEL_FALLBACK",
    "MODEL_LIVE",
    "MODEL_SMART",
    "NARRATION_MODE_DEFAULT",
    "NARRATION_MODES",
    "TokenResolution",
    "build_game_narrator",
    "complete_with_copilot_cli",
    "get_fallback_model_name",
    "get_fast_model_name",
    "get_live_model_name",
    "get_llm_router",
    "get_narration_mode",
    "get_runtime_settings",
    "get_smart_model_name",
    "resolve_copilot_token",
]
