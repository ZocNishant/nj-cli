from __future__ import annotations

from nj.models.config import LLMConfig
from nj.providers.base import BaseLLMProvider


def get_provider(config: LLMConfig) -> BaseLLMProvider:
    provider_name = config.provider.lower()

    if provider_name == "claude":
        from nj.providers.claude import ClaudeProvider
        return ClaudeProvider(
            api_key=config.api_key,
            model=config.model,
        )

    if provider_name in ("freellmapi", "openai"):
        from nj.providers.openai import OpenAICompatibleProvider
        base_url = (
            config.freellmapi_base_url
            if provider_name == "freellmapi"
            else "https://api.openai.com/v1"
        )
        api_key = (
            config.freellmapi_api_key
            if provider_name == "freellmapi"
            else config.api_key
        )
        model = (
            config.freellmapi_model
            if provider_name == "freellmapi"
            else config.model
        )
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    raise ValueError(
        f"Unknown LLM provider: '{config.provider}'. "
        f"Available: claude, freellmapi"
    )
