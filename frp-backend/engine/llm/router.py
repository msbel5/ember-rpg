"""LLM router for Copilot-backed live narration."""
from __future__ import annotations

import logging
from typing import Callable, Optional

import openai

from .auth import CopilotAuthError, resolve_copilot_token
from .cli_provider import complete_with_copilot_cli
from .settings import (
    DEFAULT_NARRATION_MODE,
    NARRATION_MODES,
    get_runtime_settings,
)

logger = logging.getLogger(__name__)


class LiveNarrationRequiredError(RuntimeError):
    """Raised when a caller explicitly requires live narration and it is unavailable."""


class LLMRouter:
    def __init__(
        self,
        client_factory: Callable[..., openai.OpenAI] = openai.OpenAI,
        token_resolver: Callable[[str], object] = resolve_copilot_token,
    ):
        self._client: Optional[openai.OpenAI] = None
        self._available: Optional[bool] = None
        self._client_factory = client_factory
        self._token_resolver = token_resolver
        self._client_signature: Optional[tuple] = None
        self._last_auth_source = "unresolved"

    @property
    def last_auth_source(self) -> str:
        return self._last_auth_source

    def _resolve_mode(self, narration_mode: Optional[str]) -> str:
        normalized = str(narration_mode or get_runtime_settings().narration_mode).strip().lower()
        return normalized if normalized in NARRATION_MODES else DEFAULT_NARRATION_MODE

    def _get_client(self, force_refresh: bool = False) -> openai.OpenAI:
        import os
        settings = get_runtime_settings()

        # Priority 1: copilot-api proxy (free models via GitHub Copilot)
        copilot_api_url = os.getenv("EMBER_COPILOT_API_URL", "http://localhost:4141/v1")
        try:
            # Quick check if copilot-api is running
            import urllib.request
            urllib.request.urlopen(copilot_api_url.replace("/v1", "") + "/v1/models", timeout=2)
            signature = ("copilot-api", copilot_api_url)
            if self._client is None or force_refresh or signature != self._client_signature:
                self._client = self._client_factory(base_url=copilot_api_url, api_key="copilot")
                self._client_signature = signature
                self._last_auth_source = "copilot_api_proxy"
            return self._client
        except Exception:
            pass  # copilot-api not running, fall through

        # Priority 2: Direct OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if openai_key:
            signature = ("openai_direct", openai_key[:8])
            if self._client is None or force_refresh or signature != self._client_signature:
                self._client = self._client_factory(api_key=openai_key)
                self._client_signature = signature
                self._last_auth_source = "env:OPENAI_API_KEY"
            return self._client

        # Priority 3: Copilot token resolution (original path)
        resolution = self._token_resolver(settings.token_path_default)
        effective_base_url = settings.base_url or None
        signature = (
            effective_base_url,
            tuple(sorted(settings.default_headers.items())),
            resolution.token,
        )
        if self._client is None or force_refresh or signature != self._client_signature:
            try:
                kwargs = {"api_key": resolution.token}
                if effective_base_url:
                    kwargs["base_url"] = effective_base_url
                if settings.default_headers:
                    kwargs["default_headers"] = settings.default_headers
                self._client = self._client_factory(**kwargs)
                self._client_signature = signature
                self._last_auth_source = resolution.source
            except Exception as exc:
                logger.warning("LLM client init failed: %s", exc)
                raise
        return self._client

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        err_str = str(exc).lower()
        return "expired" in err_str or "unauthorized" in err_str or "401" in err_str

    def _request(self, messages: list, model: str, max_tokens: int, temperature: float) -> Optional[str]:
        settings = get_runtime_settings()
        api_error: Optional[Exception] = None
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content is None:
                return None
            return content.strip()
        except Exception as exc:
            api_error = exc
            logger.info("Copilot API request failed for %s, trying CLI provider: %s", model, exc)

        try:
            result = complete_with_copilot_cli(messages, model=model, cli_command=settings.cli_command)
            self._last_auth_source = "copilot_cli"
            return result.strip()
        except Exception as cli_exc:
            if api_error is not None:
                raise cli_exc from api_error
            raise

    def _raise_live_error(self, model: str, exc: Exception) -> None:
        self._available = False
        raise LiveNarrationRequiredError(
            f"Live narration required for model {model}, but the Copilot provider is unavailable: {exc}"
        ) from exc

    def is_available(self, narration_mode: Optional[str] = None) -> bool:
        if self._available is not None and narration_mode is None:
            return self._available
        if self._resolve_mode(narration_mode) == "fallback_only":
            self._available = False
            return False
        try:
            settings = get_runtime_settings()
            result = self.complete(
                messages=[{"role": "user", "content": "ping"}],
                model=settings.live_model,
                max_tokens=5,
                temperature=0.1,
                narration_mode="require_live",
            )
            self._available = bool(result)
        except LiveNarrationRequiredError:
            self._available = False
        return bool(self._available)

    def complete(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 300,
        temperature: float = 0.8,
        narration_mode: Optional[str] = None,
    ) -> Optional[str]:
        settings = get_runtime_settings()
        mode = self._resolve_mode(narration_mode)
        requested_model = model or settings.live_model
        if mode == "fallback_only":
            self._available = False
            return None

        try:
            result = self._request(messages, requested_model, max_tokens, temperature)
            self._available = True
            return result
        except Exception as exc:
            logger.warning("LLM call failed (%s): %s", requested_model, exc)
            if self._is_auth_error(exc):
                logger.info("Refreshing Copilot client after auth failure.")
                self._client = None
                self._available = None
                try:
                    client = self._get_client(force_refresh=True)
                    response = client.chat.completions.create(
                        model=requested_model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    self._available = True
                    content = response.choices[0].message.content
                    return content.strip() if isinstance(content, str) else None
                except Exception as retry_exc:
                    logger.warning("LLM retry failed (%s): %s", requested_model, retry_exc)
                    exc = retry_exc
            if mode == "require_live":
                self._raise_live_error(requested_model, exc)

        if requested_model != settings.fallback_model:
            try:
                result = self._request(messages, settings.fallback_model, max_tokens, temperature)
                self._available = True
                logger.info("Used fallback model %s", settings.fallback_model)
                return result
            except Exception as fallback_exc:
                logger.warning("LLM fallback failed (%s): %s", settings.fallback_model, fallback_exc)
                if mode == "require_live":
                    self._raise_live_error(requested_model, fallback_exc)
        self._available = False
        return None

    def narrative(
        self,
        system_prompt: str,
        user_prompt: str,
        important: bool = False,
        narration_mode: Optional[str] = None,
    ) -> Optional[str]:
        settings = get_runtime_settings()
        model = settings.smart_model if important else settings.live_model
        return self.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            narration_mode=narration_mode,
        )


_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
