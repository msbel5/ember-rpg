"""Tests for LLM integration — uses mocking to avoid real API calls in CI."""
from unittest.mock import patch, MagicMock
import pytest


def test_llm_router_initializes():
    from engine.llm import get_llm_router
    router = get_llm_router()
    assert router is not None


def test_llm_router_complete_returns_none_on_failure():
    from engine.llm import LLMRouter
    router = LLMRouter()
    with patch.object(router, '_get_client', side_effect=Exception("no connection")):
        result = router.complete([{"role": "user", "content": "test"}])
        assert result is None


def test_llm_router_narrative_uses_haiku_by_default():
    from engine.llm import LLMRouter
    router = LLMRouter()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test narrative"
    mock_client.chat.completions.create.return_value = mock_response

    with patch.object(router, '_get_client', return_value=mock_client):
        result = router.narrative("system", "user")
        assert result == "Test narrative"
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]['model'] == 'claude-haiku-4.5'


def test_llm_router_narrative_uses_sonnet_when_important():
    from engine.llm import LLMRouter
    router = LLMRouter()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Epic battle narration"
    mock_client.chat.completions.create.return_value = mock_response

    with patch.object(router, '_get_client', return_value=mock_client):
        result = router.narrative("system", "user", important=True)
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]['model'] == 'claude-sonnet-4.6'


def test_dm_agent_falls_back_to_template_when_llm_unavailable():
    from engine.core.dm_agent import DMAIAgent, EventType
    agent = DMAIAgent()
    with patch('engine.llm.get_llm_router') as mock_router_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None  # simulate unavailable
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
    with patch('engine.llm.get_llm_router') as mock_router_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = "You step into a dark forest..."
        mock_router_fn.return_value = mock_router
        result = agent.generate_narrative_llm(
            EventType.EXPLORATION,
            {"player_name": "Hero", "location": "dark forest"},
        )
        assert result == "You step into a dark forest..."


def test_llm_status_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.get("/game/llm/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
