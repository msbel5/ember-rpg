"""
LLM Router — selects and calls the appropriate model.
Falls back gracefully when LLM is unavailable.
"""
import openai
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

COPILOT_TOKEN_PATH = '/home/msbel/.openclaw/credentials/github-copilot.token.json'
COPILOT_BASE_URL = 'https://api.githubcopilot.com'
COPILOT_HEADERS = {
    'Editor-Version': 'vscode/1.95.0',
    'Editor-Plugin-Version': 'copilot/1.240.0',
    'User-Agent': 'GithubCopilot/1.240.0',
    'Copilot-Integration-Id': 'vscode-chat'
}

# Model tiers
MODEL_FAST = 'claude-haiku-4.5'      # routine narrative, NPC dialogue
MODEL_SMART = 'claude-sonnet-4.6'    # boss encounters, key story moments
MODEL_FALLBACK = 'gpt-5-mini'        # when others unavailable


class LLMRouter:
    def __init__(self):
        self._client: Optional[openai.OpenAI] = None
        self._available = None  # None = untested

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            try:
                with open(COPILOT_TOKEN_PATH) as f:
                    token = json.load(f)['token']
                self._client = openai.OpenAI(
                    base_url=COPILOT_BASE_URL,
                    api_key=token,
                    default_headers=COPILOT_HEADERS
                )
            except Exception as e:
                logger.warning(f"LLM client init failed: {e}")
                raise
        return self._client

    def is_available(self) -> bool:
        if self._available is None:
            try:
                client = self._get_client()
                client.chat.completions.create(
                    model=MODEL_FAST,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5
                )
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def complete(self, messages: list, model: str = MODEL_FAST, max_tokens: int = 300, temperature: float = 0.8) -> Optional[str]:
        """Call LLM. Returns None if unavailable (caller falls back to template)."""
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM call failed ({model}): {e}")
            self._available = False
            return None

    def narrative(self, system_prompt: str, user_prompt: str, important: bool = False) -> Optional[str]:
        """Convenience: generate narrative. Uses haiku normally, sonnet if important=True."""
        model = MODEL_SMART if important else MODEL_FAST
        return self.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model
        )


# Module-level singleton
_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
