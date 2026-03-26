"""Tests for Copilot-backed live narration integration."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _clear_auth_env(monkeypatch) -> None:
    for env_name in (
        "EMBER_RPG_COPILOT_TOKEN",
        "COPILOT_GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "EMBER_RPG_COPILOT_TOKEN_PATH",
    ):
        monkeypatch.delenv(env_name, raising=False)


def test_llm_router_initializes():
    from engine.llm import get_llm_router

    router = get_llm_router()
    assert router is not None


def test_resolve_copilot_token_prefers_explicit_env(monkeypatch):
    from engine.llm import resolve_copilot_token

    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("EMBER_RPG_COPILOT_TOKEN", "env-token")
    monkeypatch.setenv("GH_TOKEN", "gh-token")

    resolution = resolve_copilot_token()

    assert resolution.token == "env-token"
    assert resolution.source == "env:EMBER_RPG_COPILOT_TOKEN"


def test_resolve_copilot_token_uses_gh_auth_when_env_missing(monkeypatch):
    from engine.llm import resolve_copilot_token

    _clear_auth_env(monkeypatch)
    completed = subprocess.CompletedProcess(args=["gh", "auth", "token"], returncode=0, stdout="gh-oauth\n", stderr="")
    with patch("engine.llm.auth.subprocess.run", return_value=completed):
        resolution = resolve_copilot_token()

    assert resolution.token == "gh-oauth"
    assert resolution.source == "gh_auth_token"


def test_resolve_copilot_token_uses_legacy_file_after_gh(monkeypatch, tmp_path: Path):
    from engine.llm import resolve_copilot_token

    _clear_auth_env(monkeypatch)
    token_file = tmp_path / "copilot.json"
    token_file.write_text('{"token": "file-token"}', encoding="utf-8")
    completed = subprocess.CompletedProcess(args=["gh", "auth", "token"], returncode=1, stdout="", stderr="no auth")
    with patch("engine.llm.auth.subprocess.run", return_value=completed):
        resolution = resolve_copilot_token(str(token_file))

    assert resolution.token == "file-token"
    assert resolution.source == "token_file"


def test_resolve_copilot_token_raises_when_no_source(monkeypatch):
    from engine.llm import CopilotAuthError, resolve_copilot_token

    _clear_auth_env(monkeypatch)
    completed = subprocess.CompletedProcess(args=["gh", "auth", "token"], returncode=1, stdout="", stderr="no auth")
    with patch("engine.llm.auth.subprocess.run", return_value=completed):
        with pytest.raises(CopilotAuthError):
            resolve_copilot_token()


def test_llm_router_complete_returns_none_on_failure():
    from engine.llm import LLMRouter

    router = LLMRouter()
    with patch.object(router, "_request", side_effect=Exception("no connection")):
        result = router.complete([{"role": "user", "content": "test"}])
    assert result is None


def test_llm_router_narrative_uses_gpt41_by_default():
    from engine.llm import LLMRouter

    router = LLMRouter()
    with patch.object(router, "complete", return_value="Test narrative") as complete:
        result = router.narrative("system", "user")

    assert result == "Test narrative"
    assert complete.call_args.kwargs["model"] == "gpt-4.1"


def test_llm_router_complete_uses_gpt5mini_fallback_when_allowed():
    from engine.llm import LLMRouter

    router = LLMRouter()
    with patch.object(router, "_request", side_effect=[Exception("primary down"), "Fallback text"]) as request:
        result = router.complete([{"role": "user", "content": "test"}])

    assert result == "Fallback text"
    assert request.call_args_list[0].args[1] == "gpt-4.1"
    assert request.call_args_list[1].args[1] == "gpt-5-mini"


def test_llm_router_uses_copilot_cli_when_api_provider_fails():
    from engine.llm import LLMRouter

    router = LLMRouter()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("forbidden")
    with patch.object(router, "_get_client", return_value=mock_client), patch(
        "engine.llm.router.complete_with_copilot_cli",
        return_value="CLI narration",
    ) as cli_call:
        result = router.complete([{"role": "user", "content": "test"}], narration_mode="require_live")

    assert result == "CLI narration"
    assert router.last_auth_source == "copilot_cli"
    assert cli_call.call_args.kwargs["model"] == "gpt-4.1"


def test_llm_router_require_live_raises_on_provider_failure():
    from engine.llm import LLMRouter, LiveNarrationRequiredError

    router = LLMRouter()
    with patch.object(router, "_request", side_effect=Exception("provider unavailable")):
        with pytest.raises(LiveNarrationRequiredError):
            router.complete(
                [{"role": "user", "content": "test"}],
                narration_mode="require_live",
            )


def test_llm_router_fallback_only_skips_provider_calls():
    from engine.llm import LLMRouter

    router = LLMRouter()
    with patch.object(router, "_request") as request:
        result = router.complete(
            [{"role": "user", "content": "test"}],
            narration_mode="fallback_only",
        )

    assert result is None
    request.assert_not_called()


def test_build_game_narrator_uses_live_model_and_sanitizes_output():
    from engine.llm import build_game_narrator

    mock_router = MagicMock()
    mock_router.complete.return_value = "# Title\nYou step into the ruin."
    with patch("engine.llm.builders.get_llm_router", return_value=mock_router):
        narrator = build_game_narrator()
        result = narrator("Describe the room.")

    assert result == "You step into the ruin."
    assert mock_router.complete.call_args.kwargs["model"] == "gpt-4.1"


def test_dm_agent_falls_back_to_template_when_llm_unavailable():
    from engine.core.dm_agent import DMAIAgent, EventType

    agent = DMAIAgent()
    with patch("engine.llm.get_llm_router") as mock_router_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None
        mock_router_fn.return_value = mock_router
        result = agent.generate_narrative_llm(
            EventType.EXPLORATION,
            {"player_name": "Hero", "location": "forest"},
        )

    assert isinstance(result, str)
    assert len(result) > 0


def test_dm_agent_llm_narrative_uses_llm_when_available():
    from engine.core.dm_agent import DMAIAgent, EventType

    agent = DMAIAgent()
    with patch("engine.llm.get_llm_router") as mock_router_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = "You step into a dark forest..."
        mock_router_fn.return_value = mock_router
        result = agent.generate_narrative_llm(
            EventType.EXPLORATION,
            {"player_name": "Hero", "location": "dark forest"},
        )

    assert result == "You step into a dark forest..."


def test_llm_status_endpoint_reports_live_config():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    mock_router = MagicMock()
    mock_router.narrative.return_value = "The corridor breathes cold air."
    mock_router.last_auth_source = "gh_auth_token"

    with patch("engine.llm.get_llm_router", return_value=mock_router), patch(
        "engine.llm.get_narration_mode", return_value="prefer_live"
    ), patch("engine.llm.get_live_model_name", return_value="gpt-4.1"), patch(
        "engine.llm.get_fallback_model_name", return_value="gpt-5-mini"
    ):
        resp = client.get("/game/llm/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["mode"] == "prefer_live"
    assert data["model"] == "gpt-4.1"
    assert data["fallback_model"] == "gpt-5-mini"
    assert data["auth_source"] == "gh_auth_token"
