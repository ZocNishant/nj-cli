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


def test_registry_freellmapi_supports_json_mode():
    """It does now — `complete()` sends response_format and steps down on a 400.

    This asserted False while LLMRequest.json_schema was being dropped on the
    floor, so SCORE_SCHEMA and REVIEW_SCHEMA were built, passed and never
    enforced on the provider the project actually runs on.
    """
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="test-key",
    )
    provider = get_provider(config)
    assert provider.supports_json_mode() is True


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


def test_registry_openai_honours_the_model_tiers():
    """The OpenAI path must tier like the Claude path.

    It used to read config.model for every task, which collapsed scoring,
    tailoring, review and reasoning onto one model — and made the reviewer the
    same model as the drafter it is meant to audit.
    """
    config = LLMConfig(
        provider="openai",
        api_key="sk-test",
        model="fallback-model",
        scoring_model="scoring-model",
        tailoring_model="tailoring-model",
        review_model="review-model",
        reasoning_model="reasoning-model",
    )
    assert get_provider(config, task="scoring").model == "scoring-model"
    assert get_provider(config, task="tailoring").model == "tailoring-model"
    assert get_provider(config, task="review").model == "review-model"
    assert get_provider(config, task="reasoning").model == "reasoning-model"
    # An unrecognised task still falls back to the generic model.
    assert get_provider(config, task="nonsense").model == "fallback-model"
    assert get_provider(config).model == "fallback-model"


def test_registry_openai_drafter_and_reviewer_are_different_models():
    """The asymmetry the drafter-reviewer split depends on, on the OpenAI path."""
    config = LLMConfig(
        provider="openai",
        api_key="sk-test",
        tailoring_model="big-model",
        review_model="cheap-model",
    )
    drafter = get_provider(config, task="tailoring")
    reviewer = get_provider(config, task="review")
    assert drafter.model != reviewer.model


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


# --- parameter adaptation ---
#
# Newer OpenAI models reject `max_tokens` (requiring `max_completion_tokens`)
# and some reject `temperature`. Groq and older models want the old spelling.
# The provider learns the shape from the first 400 rather than carrying a
# model-family list that goes stale on every release.


def _param_error(param: str):
    return Exception(
        f"Error code: 400 - {{'error': {{'message': \"Unsupported parameter: "
        f"'{param}' is not supported with this model.\"}}}}"
    )


@pytest.mark.asyncio
async def test_provider_switches_to_max_completion_tokens_on_rejection():
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="gpt-5.5")
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        if "max_tokens" in kwargs:
            raise _param_error("max_tokens")
        return make_openai_response('{"ok": true}', model="gpt-5.5")

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=create)
    with patch.object(provider, "_get_client", return_value=client):
        result = await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))

    assert result.content == '{"ok": true}'
    assert "max_tokens" in calls[0]
    assert calls[1]["max_completion_tokens"] == 500
    assert provider._token_param == "max_completion_tokens"


@pytest.mark.asyncio
async def test_provider_drops_temperature_when_rejected():
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="o3")
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        if "temperature" in kwargs:
            raise _param_error("temperature")
        return make_openai_response('{"ok": true}', model="o3")

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=create)
    with patch.object(provider, "_get_client", return_value=client):
        await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))

    assert "temperature" not in calls[-1]
    assert provider._send_temperature is False


@pytest.mark.asyncio
async def test_provider_remembers_the_shape_across_calls():
    """The adaptation must be paid once, not on all 200 scoring calls in a run."""
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="gpt-5.5")
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        if "max_tokens" in kwargs:
            raise _param_error("max_tokens")
        return make_openai_response('{"ok": true}', model="gpt-5.5")

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=create)
    with patch.object(provider, "_get_client", return_value=client):
        await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))
        await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))

    # 2 for the first call (one rejected, one accepted), 1 for the second.
    assert len(calls) == 3
    assert "max_tokens" not in calls[2]


@pytest.mark.asyncio
async def test_provider_keeps_max_tokens_when_the_model_accepts_it():
    """Groq and older OpenAI models must be unaffected by the adaptation."""
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="gpt-4o-mini")
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        return make_openai_response('{"ok": true}', model="gpt-4o-mini")

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=create)
    with patch.object(provider, "_get_client", return_value=client):
        await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))

    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 500
    assert provider._token_param == "max_tokens"


@pytest.mark.asyncio
async def test_provider_reraises_an_error_it_cannot_adapt_to():
    """A 404 for a non-chat model must surface, not spin through retries."""
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="gpt-5.5-pro")
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=Exception("Error code: 404 - This is not a chat model")
    )
    with patch.object(provider, "_get_client", return_value=client):
        with pytest.raises(Exception, match="not a chat model"):
            await provider.complete(LLMRequest(system="s", user="u", max_tokens=500))
    assert client.chat.completions.create.await_count == 1


# --- the gateway path must tier like the others ----------------------------
#
# resolve_model was bypassed for provider=freellmapi, so all four tasks got
# freellmapi_model. The reviewer then audited a draft written by itself.


def test_gateway_path_resolves_a_model_per_task():
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="k",
        freellmapi_model="fallback-model",
        scoring_model="cheap-model",
        tailoring_model="strong-model",
        review_model="cheap-model",
        reasoning_model="reasoning-model",
    )
    assert get_provider(config, task="scoring").model == "cheap-model"
    assert get_provider(config, task="tailoring").model == "strong-model"
    assert get_provider(config, task="reasoning").model == "reasoning-model"


def test_the_gateway_reviewer_is_not_the_drafter():
    """The invariant the drafter-reviewer split depends on."""
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="k",
        freellmapi_model="fallback-model",
        tailoring_model="strong-model",
        review_model="cheap-model",
    )
    drafter = get_provider(config, task="tailoring")
    reviewer = get_provider(config, task="review")
    assert drafter.model != reviewer.model


def test_freellmapi_model_is_still_the_fallback_for_an_untiered_task():
    config = LLMConfig(
        provider="freellmapi",
        freellmapi_api_key="k",
        freellmapi_model="fallback-model",
        scoring_model="",
    )
    assert get_provider(config, task="scoring").model == "fallback-model"
    assert get_provider(config).model == "fallback-model"
