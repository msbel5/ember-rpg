"""Public LLM package surface."""
from __future__ import annotations

from .auth import CopilotAuthError, TokenResolution, resolve_copilot_token
from .builders import build_game_narrator
from .cli_provider import CopilotCLIError, complete_with_copilot_cli
from .router import LLMRouter, LiveNarrationRequiredError, get_llm_router
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

_SETTINGS = get_runtime_settings()

MODEL_LIVE = _SETTINGS.live_model
MODEL_FAST = _SETTINGS.fast_model
MODEL_SMART = _SETTINGS.smart_model
MODEL_FALLBACK = _SETTINGS.fallback_model
NARRATION_MODE_DEFAULT = _SETTINGS.narration_mode

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
