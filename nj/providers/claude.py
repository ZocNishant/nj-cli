from __future__ import annotations

import time

import anthropic

from nj.providers.base import BaseLLMProvider, LLMRequest, LLMResponse


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def name(self) -> str:
        return "claude"

    def supports_json_mode(self) -> bool:
        return True

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        message = self.client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=message.content[0].text,
            provider="claude",
            model=self.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
        )
