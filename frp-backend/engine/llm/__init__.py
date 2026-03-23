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

    def _load_token(self) -> str:
        """Load fresh token from disk each time (token rotates)."""
        with open(COPILOT_TOKEN_PATH) as f:
            return json.load(f)['token']

    def _get_client(self, force_refresh: bool = False) -> openai.OpenAI:
        if self._client is None or force_refresh:
            try:
                token = self._load_token()
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
        """Call LLM. Returns None if unavailable (caller falls back to template).
        
        On token expiry: resets client and retries once with fresh token.
        On failure: tries MODEL_FALLBACK before giving up.
        """
        # Attempt 1: current client + requested model
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            self._available = True
            return resp.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e).lower()
            logger.warning(f"LLM call failed ({model}): {e}")

            # Token expired — reset client and retry with fresh token
            if 'expired' in err_str or 'unauthorized' in err_str or '401' in err_str:
                logger.info("Token expired, refreshing client...")
                self._client = None
                self._available = None
                try:
                    client = self._get_client(force_refresh=True)
                    resp = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    self._available = True
                    return resp.choices[0].message.content.strip()
                except Exception as e2:
                    logger.warning(f"LLM retry failed ({model}): {e2}")

        # Attempt 2: fallback model (gpt-5-mini — free tier)
        if model != MODEL_FALLBACK:
            try:
                client = self._get_client()
                resp = client.chat.completions.create(
                    model=MODEL_FALLBACK,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                self._available = True
                logger.info(f"Used fallback model {MODEL_FALLBACK}")
                return resp.choices[0].message.content.strip()
            except Exception as e3:
                logger.warning(f"LLM fallback failed ({MODEL_FALLBACK}): {e3}")

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
