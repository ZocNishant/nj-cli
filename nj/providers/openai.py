from __future__ import annotations

from nj.providers.base import BaseLLMProvider, LLMRequest, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    def name(self) -> str:
        return "openai"

    def supports_json_mode(self) -> bool:
        return True

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError(
            "OpenAI provider is not yet implemented. "
            "See docs/adding-a-provider.md to implement it. "
            "Use provider: claude in config.yaml for now."
        )
