from __future__ import annotations

import os

from nj.models.config import LLMConfig
from nj.providers.base import BaseLLMProvider


def get_provider(config: LLMConfig) -> BaseLLMProvider:
    provider_name = config.provider.lower()

    if provider_name == "claude":
        from nj.providers.claude import ClaudeProvider

        api_key = os.getenv("ANTHROPIC_API_KEY") or config.api_key
        return ClaudeProvider(api_key=api_key, model=config.model)

    if provider_name in ("freellmapi", "openai"):
        from nj.providers.openai import OpenAICompatibleProvider

        if provider_name == "freellmapi":
            base_url = config.freellmapi_base_url
            # GROQ_API_KEY or FREELLMAPI_API_KEY in .env both work
            api_key = (
                os.getenv("GROQ_API_KEY")
                or os.getenv("FREELLMAPI_API_KEY")
                or config.freellmapi_api_key
            )
            model = config.freellmapi_model
        else:
            base_url = "https://api.openai.com/v1"
            api_key = os.getenv("OPENAI_API_KEY") or config.api_key
            model = config.model

        return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)

    raise ValueError(
        f"Unknown LLM provider: '{config.provider}'. " f"Available: claude, freellmapi"
    )
