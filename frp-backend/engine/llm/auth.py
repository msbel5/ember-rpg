"""Auth resolution for the Copilot-backed LLM provider."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ENV_TOKEN_NAMES = (
    "EMBER_RPG_COPILOT_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


class CopilotAuthError(RuntimeError):
    """Raised when no supported Copilot auth source can be resolved."""


@dataclass(frozen=True)
class TokenResolution:
    token: str
    source: str


def _resolve_env_token() -> Optional[TokenResolution]:
    for env_name in ENV_TOKEN_NAMES:
        token = str(os.getenv(env_name, "")).strip()
        if token:
            return TokenResolution(token=token, source=f"env:{env_name}")
    return None


def _resolve_gh_token() -> Optional[TokenResolution]:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    if not token:
        return None
    return TokenResolution(token=token, source="gh_auth_token")


def _resolve_token_file(token_path: str) -> TokenResolution:
    try:
        payload = json.loads(Path(token_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CopilotAuthError(f"Copilot token file not found: {token_path}") from exc
    except json.JSONDecodeError as exc:
        raise CopilotAuthError(f"Copilot token file is not valid JSON: {token_path}") from exc
    token = str(payload.get("token", "")).strip()
    if not token:
        raise CopilotAuthError(f"Copilot token file does not contain a usable token: {token_path}")
    return TokenResolution(token=token, source="token_file")


def resolve_copilot_token(token_path_default: str = "") -> TokenResolution:
    env_token = _resolve_env_token()
    if env_token is not None:
        return env_token

    gh_token = _resolve_gh_token()
    if gh_token is not None:
        return gh_token

    token_path = str(os.getenv("EMBER_RPG_COPILOT_TOKEN_PATH") or token_path_default).strip()
    if token_path:
        return _resolve_token_file(token_path)

    env_hint = ", ".join(ENV_TOKEN_NAMES)
    raise CopilotAuthError(
        "No Copilot auth source configured. Set one of "
        f"{env_hint}, log in with `gh auth login`, or configure EMBER_RPG_COPILOT_TOKEN_PATH."
    )
