from __future__ import annotations

import time

from nj.providers.base import BaseLLMProvider, LLMRequest, LLMResponse


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

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError(
                    "openai package required for FreeLLMAPI: "
                    "pip install openai"
                )
        return self._client

    def name(self) -> str:
        return "freellmapi"

    def supports_json_mode(self) -> bool:
        return False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.monotonic()
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
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
