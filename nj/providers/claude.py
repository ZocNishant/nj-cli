from __future__ import annotations

import time

import anthropic

from nj.providers.base import BaseLLMProvider, LLMRequest, LLMResponse
from nj.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"


class ClaudeProvider(BaseLLMProvider):
    """Anthropic provider.

    Three things differ from the previous implementation:

    * It uses AsyncAnthropic. The old code declared `complete` as async but
      called the synchronous client inside it, so every "parallel" scoring task
      blocked the event loop and the run was serial in practice.
    * It sends `output_config.format` when the caller supplies a schema, so the
      model is constrained to valid JSON rather than asked nicely for it.
    * It never sends `temperature`. Sonnet 5 and Opus 5 reject sampling
      parameters with a 400.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_retries: int = 4,
        timeout: float = 120.0,
    ):
        # The SDK retries 408/409/429/5xx with exponential backoff itself, which
        # is what we want for a long scoring run against rate limits.
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.model = model

    def name(self) -> str:
        return "claude"

    def supports_json_mode(self) -> bool:
        return True

    def _build_system(self, request: LLMRequest) -> list[dict]:
        block: dict = {"type": "text", "text": request.system}
        if request.cache_system:
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()

        kwargs: dict = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": self._build_system(request),
            "messages": [{"role": "user", "content": request.user}],
        }
        if request.json_schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": request.json_schema}
            }

        message = await self.client.messages.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        # A refusal returns HTTP 200 with an empty/partial content list, so
        # indexing content[0] unconditionally would raise here rather than
        # surfacing what actually happened.
        if message.stop_reason == "refusal":
            logger.warning("claude_refusal", model=self.model)
            raise RuntimeError("Claude declined this request (stop_reason=refusal)")

        text = next((b.text for b in message.content if b.type == "text"), "")
        if not text:
            raise RuntimeError(f"Claude returned no text block (stop_reason={message.stop_reason})")

        usage = message.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        if cache_read:
            logger.debug("prompt_cache_hit", tokens=cache_read, model=self.model)

        return LLMResponse(
            content=text,
            provider="claude",
            model=self.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=latency_ms,
        )
