"""Runtime configuration helpers for the Copilot-backed LLM stack."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

from engine.data_loader import get_llm_runtime_config

DEFAULT_LIVE_MODEL = "gpt-4.1"
DEFAULT_FAST_MODEL = "gpt-5-mini"
DEFAULT_NARRATION_MODE = "prefer_live"
NARRATION_MODES = frozenset({"prefer_live", "require_live", "fallback_only"})


@dataclass(frozen=True)
class LLMRuntimeSettings:
    base_url: str
    default_headers: Dict[str, str]
    token_path_default: str
    cli_command: str
    live_model: str
    smart_model: str
    fast_model: str
    fallback_model: str
    narration_mode: str


def _normalize_mode(raw_mode: str) -> str:
    normalized = str(raw_mode or DEFAULT_NARRATION_MODE).strip().lower()
    return normalized if normalized in NARRATION_MODES else DEFAULT_NARRATION_MODE


def get_runtime_settings() -> LLMRuntimeSettings:
    config = get_llm_runtime_config()
    copilot_config = dict(config.get("copilot", {}))
    model_config = dict(config.get("models", {}))

    live_model = str(
        os.getenv("EMBER_RPG_LLM_LIVE_MODEL")
        or model_config.get("live")
        or model_config.get("smart")
        or DEFAULT_LIVE_MODEL
    )
    fast_model = str(
        os.getenv("EMBER_RPG_LLM_FAST_MODEL")
        or model_config.get("fast")
        or DEFAULT_FAST_MODEL
    )
    smart_model = str(
        os.getenv("EMBER_RPG_LLM_SMART_MODEL")
        or model_config.get("smart")
        or live_model
    )
    fallback_model = str(
        os.getenv("EMBER_RPG_LLM_FALLBACK_MODEL")
        or model_config.get("fallback")
        or fast_model
    )

    return LLMRuntimeSettings(
        base_url=str(os.getenv("EMBER_RPG_LLM_BASE_URL") or copilot_config.get("base_url", "")).strip(),
        default_headers={str(key): str(value) for key, value in dict(copilot_config.get("default_headers", {})).items()},
        token_path_default=str(copilot_config.get("token_path_default", "")).strip(),
        cli_command=str(os.getenv("EMBER_RPG_COPILOT_CLI_PATH") or copilot_config.get("cli_command_default", "copilot")).strip(),
        live_model=live_model,
        smart_model=smart_model,
        fast_model=fast_model,
        fallback_model=fallback_model,
        narration_mode=_normalize_mode(
            str(os.getenv("EMBER_RPG_LLM_MODE") or config.get("narration_mode_default") or DEFAULT_NARRATION_MODE)
        ),
    )


def get_live_model_name() -> str:
    return get_runtime_settings().live_model


def get_fast_model_name() -> str:
    return get_runtime_settings().fast_model


def get_smart_model_name() -> str:
    return get_runtime_settings().smart_model


def get_fallback_model_name() -> str:
    return get_runtime_settings().fallback_model


def get_narration_mode() -> str:
    return get_runtime_settings().narration_mode
