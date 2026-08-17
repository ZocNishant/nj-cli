from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nj.models.config import LLMConfig
from nj.providers.base import LLMRequest
from nj.providers.openai import OpenAICompatibleProvider, OpenAIProvider
from nj.providers.registry import get_provider


def make_openai_response(content: str, model: str = "gemini-pro"):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.model = model
    response.usage = MagicMock()
    response.usage.prompt_tokens = 50
    response.usage.completion_tokens = 20
    return response


@pytest.mark.asyncio
async def test_freellmapi_complete_returns_response():
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="http://localhost:3001/v1",
        model="auto",
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=make_openai_response('{"score": 75}')
    )
    with patch.object(provider, "_get_client", return_value=mock_client):
        request = LLMRequest(
            system="You are helpful.",
            user="Score this job.",
            max_tokens=100,
        )
        response = await provider.complete(request)
    assert response.content == '{"score": 75}'
    assert response.provider == "freellmapi"
    assert response.input_tokens == 50
    assert response.output_tokens == 20
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_freellmapi_includes_system_message():
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="http://localhost:3001/v1",
        model="auto",
    )
    mock_client = MagicMock()
    captured_messages = []

    async def capture(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return make_openai_response("READY")

    mock_client.chat.completions.create = capture
    with patch.object(provider, "_get_client", return_value=mock_client):
        await provider.complete(
            LLMRequest(
                system="System prompt here.",
                user="User message here.",
                max_tokens=10,
            )
        )
    assert any(m["role"] == "system" for m in captured_messages)
    assert any(m["role"] == "user" for m in captured_messages)


@pytest.mark.asyncio
async def test_freellmapi_no_system_when_empty():
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="http://localhost:3001/v1",
        model="auto",
    )
    mock_client = MagicMock()
    captured_messages = []

    async def capture(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return make_openai_response("ok")

    mock_client.chat.completions.create = capture
    with patch.object(provider, "_get_client", return_value=mock_client):
        await provider.complete(
            LLMRequest(
                system="",
                user="Just a user message.",
                max_tokens=10,
            )
        )
    roles = [m["role"] for m in captured_messages]
    assert "system" not in roles
    assert "user" in roles


def test_registry_returns_freellmapi_provider():
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="test-key",
        freellmapi_base_url="http://localhost:3001/v1",
        freellmapi_model="auto",
    )
    provider = get_provider(config)
    assert provider.name() == "freellmapi"


def test_registry_freellmapi_supports_json_mode_false():
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="test-key",
    )
    provider = get_provider(config)
    assert provider.supports_json_mode() is False


def test_registry_claude_unchanged():
    with patch("nj.providers.claude.anthropic.Anthropic"):
        config = LLMConfig(
            provider="claude",
            api_key="sk-ant-test",
        )
        provider = get_provider(config)
        assert provider.name() == "claude"


def test_registry_raises_for_unknown():
    config = LLMConfig(provider="gemini", api_key="")
    with pytest.raises(ValueError) as exc:
        get_provider(config)
    assert "gemini" in str(exc.value)
    assert "claude" in str(exc.value)


def test_openai_alias_works():
    assert OpenAIProvider is OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_import_error_on_missing_openai():
    provider = OpenAICompatibleProvider(
        api_key="key",
        base_url="http://localhost:3001/v1",
    )
    with patch.dict("sys.modules", {"openai": None}):
        provider._client = None
        with pytest.raises((ImportError, Exception)):
            provider._get_client()
