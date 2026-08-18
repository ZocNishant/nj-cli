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

# Reasoning models spend tokens thinking before they emit a character, and that
# spend counts against `max_completion_tokens`. A budget sized for the visible
# answer alone is therefore consumed entirely by reasoning and the call returns
# `finish_reason="length"` with an EMPTY string — not an error, just nothing.
# Measured on gpt-5.5: a trivial 150-word request burned 600-1200 reasoning
# tokens, so every call site under ~2k silently produced "".
#
# `max_tokens` on LLMRequest means "tokens of visible output I want", so for
# these models the provider adds headroom on top. Which models need it is
# learned from the first empty-with-reasoning response rather than hardcoded,
# for the same reason the parameter shape is: a model list goes stale.
_MIN_REASONING_HEADROOM = 2048


def _rejects(message: str, param: str) -> bool:
    m = message.lower()
    return param in m and ("unsupported" in m or "not supported" in m or "use '" in m)


def _reasoning_tokens(usage) -> int:
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    return getattr(details, "reasoning_tokens", 0) or 0


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
        self._reasoning_headroom = 0

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
        """The provider this client is actually talking to.

        This returned the constant "freellmapi" for every instance, including
        the OpenAI ones, and `score_job` writes it into
        `score_results.provider` — so every score OpenAI produced was recorded
        as having come from Groq. Derived from the base URL instead, because
        that is the only thing that distinguishes them at runtime.
        """
        host = (self.base_url or "").lower()
        if "api.openai.com" in host:
            return "openai"
        if "groq.com" in host:
            return "groq"
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

    def _learn_headroom(self, response) -> bool:
        """Grow the reasoning allowance after a budget-starved empty response.

        True if something changed and the call is worth retrying. Only ever
        grows, and only on the exact signature of the failure it fixes — an
        empty answer that stopped on `length` having spent tokens reasoning.
        """
        choice = response.choices[0]
        if (choice.message.content or "").strip():
            return False
        if choice.finish_reason != "length":
            return False
        spent = _reasoning_tokens(response.usage)
        if spent <= 0:
            return False

        # The next call reasons about a different prompt and may think longer,
        # so budget well past what this one happened to spend.
        headroom = max(_MIN_REASONING_HEADROOM, spent * 2)
        if headroom <= self._reasoning_headroom:
            return False
        self._reasoning_headroom = headroom
        logger.debug(
            "openai_reasoning_headroom_learned",
            model=self.model,
            reasoning_tokens=spent,
            headroom=headroom,
        )
        return True

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.monotonic()
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})

        # At most one retry per adaptable parameter, then the error is real.
        # `_learn_headroom` can also ask for one more pass, so the ceiling
        # covers both kinds of adaptation.
        for _ in range(4):
            kwargs: dict = {
                "model": self.model,
                "messages": messages,
                self._token_param: request.max_tokens + self._reasoning_headroom,
            }
            if self._send_temperature:
                kwargs["temperature"] = request.temperature
            try:
                response = await client.chat.completions.create(**kwargs)
            except Exception as e:
                if not self._adapt_to(e):
                    raise
                continue
            # A 200 that carries no text is still a failed call: retry it with
            # room to think rather than handing "" back to a JSON parser.
            if self._learn_headroom(response):
                continue
            break
        else:  # pragma: no cover - four adaptations without success
            raise RuntimeError(f"{self.model} rejected every parameter shape tried")

        latency_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""
        model_used = response.model or self.model
        usage = response.usage
        return LLMResponse(
            content=content,
            provider=self.name(),
            model=model_used,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )


OpenAIProvider = OpenAICompatibleProvider
