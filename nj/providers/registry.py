from __future__ import annotations

from nj.models.config import LLMConfig
from nj.providers.base import BaseLLMProvider
from nj.providers.claude import ClaudeProvider
from nj.providers.openai import OpenAIProvider


def get_provider(config: LLMConfig) -> BaseLLMProvider:
    providers = {
        "claude": lambda: ClaudeProvider(
            api_key=config.api_key,
            model=config.model,
        ),
        "openai": lambda: OpenAIProvider(),
    }
    factory = providers.get(config.provider.lower())
    if not factory:
        raise ValueError(
            f"Unknown LLM provider: '{config.provider}'. "
            f"Available: {list(providers.keys())}"
        )
    return factory()
