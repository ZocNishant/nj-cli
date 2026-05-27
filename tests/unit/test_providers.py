from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from nj.models.config import LLMConfig
from nj.providers.base import LLMRequest
from nj.providers.claude import ClaudeProvider
from nj.providers.openai import OpenAICompatibleProvider, OpenAIProvider
from nj.providers.registry import get_provider


@pytest.fixture
def mock_anthropic_response() -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock(text='{"score": 85}')]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


@pytest.mark.asyncio
async def test_claude_provider_complete(mock_anthropic_response: MagicMock) -> None:
    with patch("nj.providers.claude.anthropic.Anthropic") as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_client_class.return_value = mock_client

        provider = ClaudeProvider(api_key="test-key")
        request = LLMRequest(system="You are helpful", user="Score this job")
        response = await provider.complete(request)

    assert response.content == '{"score": 85}'
    assert response.provider == "claude"
    assert response.input_tokens == 100
    assert response.output_tokens == 50
    assert response.latency_ms >= 0


def test_openai_compatible_provider_has_correct_name() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test",
        base_url="http://localhost:3001/v1",
    )
    assert provider.name() == "freellmapi"


def test_registry_returns_claude_provider() -> None:
    config = LLMConfig(provider="claude", api_key="test-key", model="claude-sonnet-4-20250514")
    with patch("nj.providers.claude.anthropic.Anthropic"):
        provider = get_provider(config)
    assert provider.name() == "claude"


def test_registry_returns_freellmapi_provider() -> None:
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="test-key",
        freellmapi_base_url="http://localhost:3001/v1",
    )
    provider = get_provider(config)
    assert provider.name() == "freellmapi"


def test_registry_raises_for_unknown_provider() -> None:
    config = LLMConfig(provider="gemini", api_key="")
    with pytest.raises(ValueError) as exc_info:
        get_provider(config)
    assert "gemini" in str(exc_info.value)
    assert "claude" in str(exc_info.value)


def test_claude_provider_name() -> None:
    with patch("nj.providers.claude.anthropic.Anthropic"):
        provider = ClaudeProvider(api_key="test")
    assert provider.name() == "claude"


def test_claude_supports_json_mode() -> None:
    with patch("nj.providers.claude.anthropic.Anthropic"):
        provider = ClaudeProvider(api_key="test")
    assert provider.supports_json_mode() is True


def test_openai_alias_is_compatible_provider() -> None:
    assert OpenAIProvider is OpenAICompatibleProvider
