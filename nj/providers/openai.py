from __future__ import annotations

import time

from nj.providers.base import BaseLLMProvider, LLMRequest, LLMResponse
from nj.utils.logger import get_logger

logger = get_logger(__name__)

# Newer OpenAI models reject `max_tokens` and require `max_completion_tokens`,
# and several reject `temperature` outright. Groq and older OpenAI models want
# the old spelling. Rather than hardcode a model-family list that goes stale on
# every release, the provider learns the accepted shape from the first 400 and
# remembers it for the rest of the process.
_TOKEN_PARAM_LEGACY = "max_tokens"
_TOKEN_PARAM_MODERN = "max_completion_tokens"


def _rejects(message: str, param: str) -> bool:
    m = message.lower()
    return param in m and ("unsupported" in m or "not supported" in m or "use '" in m)


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "auto",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None
        # Learned on first use; see the module comment.
        self._token_param = _TOKEN_PARAM_LEGACY
        self._send_temperature = True

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("openai package required for FreeLLMAPI: pip install openai")
        return self._client

    def name(self) -> str:
        return "freellmapi"

    def supports_json_mode(self) -> bool:
        return False

    def _adapt_to(self, error: Exception) -> bool:
        """Learn the parameter shape this model accepts. True if something changed.

        Only ever *narrows* what is sent — swaps the token parameter spelling or
        drops temperature — so a retry can never widen the request into a second
        different failure.
        """
        message = str(error)
        if _rejects(message, _TOKEN_PARAM_LEGACY) and self._token_param == _TOKEN_PARAM_LEGACY:
            self._token_param = _TOKEN_PARAM_MODERN
            logger.debug("openai_param_adapted", model=self.model, param=_TOKEN_PARAM_MODERN)
            return True
        if _rejects(message, _TOKEN_PARAM_MODERN) and self._token_param == _TOKEN_PARAM_MODERN:
            self._token_param = _TOKEN_PARAM_LEGACY
            logger.debug("openai_param_adapted", model=self.model, param=_TOKEN_PARAM_LEGACY)
            return True
        if _rejects(message, "temperature") and self._send_temperature:
            self._send_temperature = False
            logger.debug("openai_temperature_dropped", model=self.model)
            return True
        return False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.monotonic()
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})

        # At most one retry per adaptable parameter, then the error is real.
        for _ in range(3):
            kwargs: dict = {
                "model": self.model,
                "messages": messages,
                self._token_param: request.max_tokens,
            }
            if self._send_temperature:
                kwargs["temperature"] = request.temperature
            try:
                response = await client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                if not self._adapt_to(e):
                    raise
        else:  # pragma: no cover - three adaptations without success
            raise RuntimeError(f"{self.model} rejected every parameter shape tried")

        latency_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""
        model_used = response.model or self.model
        usage = response.usage
        return LLMResponse(
            content=content,
            provider="freellmapi",
            model=model_used,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )


OpenAIProvider = OpenAICompatibleProvider
