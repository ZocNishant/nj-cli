from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nj.models.config import LLMConfig
from nj.providers.base import LLMRequest
from nj.providers.claude import ClaudeProvider
from nj.providers.openai import OpenAICompatibleProvider, OpenAIProvider
from nj.providers.registry import get_provider, resolve_model


def _text_block(text: str) -> MagicMock:
    """A content block that satisfies `block.type == "text"`.

    A bare MagicMock returns a MagicMock for `.type`, which never equals
    "text", so the provider would treat the response as empty.
    """
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _message(
    text: str = '{"score": 85}',
    stop_reason: str = "end_turn",
    cache_read: int = 0,
) -> MagicMock:
    message = MagicMock()
    message.stop_reason = stop_reason
    message.content = [_text_block(text)] if text else []
    message.usage.input_tokens = 100
    message.usage.output_tokens = 50
    message.usage.cache_read_input_tokens = cache_read
    return message


@pytest.fixture
def mock_async_client():
    """Patch AsyncAnthropic and yield (client, captured create kwargs).

    Every test in this module goes through here — no unit test may reach the
    network. `messages.create` is awaited, so it has to be an AsyncMock.
    """
    with patch("nj.providers.claude.anthropic.AsyncAnthropic") as client_class:
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=_message())
        client_class.return_value = client
        yield client


async def test_claude_provider_complete(mock_async_client) -> None:
    provider = ClaudeProvider(api_key="test-key")
    response = await provider.complete(LLMRequest(system="You are helpful", user="Score this job"))

    assert response.content == '{"score": 85}'
    assert response.provider == "claude"
    assert response.input_tokens == 100
    assert response.output_tokens == 50
    assert response.latency_ms >= 0


async def test_claude_provider_never_sends_temperature(mock_async_client) -> None:
    """Sonnet 5 and Opus 5 reject sampling parameters with a 400."""
    provider = ClaudeProvider(api_key="test-key")
    await provider.complete(LLMRequest(system="s", user="u", temperature=0.7))

    kwargs = mock_async_client.messages.create.call_args.kwargs
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert "top_k" not in kwargs


async def test_json_schema_becomes_output_config(mock_async_client) -> None:
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    provider = ClaudeProvider(api_key="test-key")
    await provider.complete(LLMRequest(system="s", user="u", json_schema=schema))

    kwargs = mock_async_client.messages.create.call_args.kwargs
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    # Compared by value, not identity: Pydantic copies the dict on validation.
    assert kwargs["output_config"]["format"]["schema"] == schema


async def test_no_output_config_without_schema(mock_async_client) -> None:
    provider = ClaudeProvider(api_key="test-key")
    await provider.complete(LLMRequest(system="s", user="u"))

    assert "output_config" not in mock_async_client.messages.create.call_args.kwargs


async def test_cache_system_marks_the_system_block(mock_async_client) -> None:
    provider = ClaudeProvider(api_key="test-key")
    await provider.complete(LLMRequest(system="rubric + CV", user="u", cache_system=True))

    system = mock_async_client.messages.create.call_args.kwargs["system"]
    assert system[0]["text"] == "rubric + CV"
    assert system[0]["cache_control"] == {"type": "ephemeral"}


async def test_system_block_uncached_by_default(mock_async_client) -> None:
    provider = ClaudeProvider(api_key="test-key")
    await provider.complete(LLMRequest(system="s", user="u"))

    system = mock_async_client.messages.create.call_args.kwargs["system"]
    assert "cache_control" not in system[0]


async def test_refusal_raises_rather_than_indexing_empty_content(mock_async_client) -> None:
    """A refusal is HTTP 200 with no text block; content[0] would raise IndexError."""
    mock_async_client.messages.create.return_value = _message(text="", stop_reason="refusal")
    provider = ClaudeProvider(api_key="test-key")

    with pytest.raises(RuntimeError, match="refusal"):
        await provider.complete(LLMRequest(system="s", user="u"))


async def test_empty_response_raises(mock_async_client) -> None:
    mock_async_client.messages.create.return_value = _message(text="", stop_reason="end_turn")
    provider = ClaudeProvider(api_key="test-key")

    with pytest.raises(RuntimeError, match="no text block"):
        await provider.complete(LLMRequest(system="s", user="u"))


def test_openai_compatible_provider_has_correct_name() -> None:
    provider = OpenAICompatibleProvider(
        api_key="test",
        base_url="http://localhost:3001/v1",
    )
    assert provider.name() == "freellmapi"


# --- reasoning-token headroom ---
#
# A reasoning model spends tokens thinking before it writes anything, and that
# spend counts against `max_completion_tokens`. Budgets sized for the visible
# answer alone came back as `finish_reason="length"` with an EMPTY string — a
# 200, not an error — so scoring fed "" to a JSON parser and reported 0/100 for
# weeks, and every cover letter was blank. Measured on gpt-5.5: 600 and 1200
# both returned 0 characters, 2500 worked.


def _chat_completion(content: str, finish_reason: str = "stop", reasoning: int = 0) -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = finish_reason
    response.choices = [choice]
    response.model = "gpt-5.5"
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    response.usage.completion_tokens_details.reasoning_tokens = reasoning
    return response


def _openai_provider_with(responses: list[MagicMock]):
    """Provider whose client returns `responses` in order; returns (provider, calls)."""
    provider = OpenAICompatibleProvider(api_key="t", base_url="http://x/v1", model="gpt-5.5")
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        return responses[len(calls) - 1]

    client = MagicMock()
    client.chat.completions.create = create
    provider._client = client
    return provider, calls


async def test_empty_reasoning_response_is_retried_with_headroom() -> None:
    provider, calls = _openai_provider_with(
        [
            _chat_completion("", finish_reason="length", reasoning=600),
            _chat_completion("The letter."),
        ]
    )

    response = await provider.complete(LLMRequest(system="s", user="u", max_tokens=600))

    assert response.content == "The letter."
    assert len(calls) == 2
    # The retry must actually ask for more room, or it just fails again.
    assert calls[1]["max_tokens"] > calls[0]["max_tokens"]


async def test_headroom_is_remembered_for_later_calls() -> None:
    """Learned once per process: the second call must not repeat the empty one."""
    provider, calls = _openai_provider_with(
        [
            _chat_completion("", finish_reason="length", reasoning=600),
            _chat_completion("first"),
            _chat_completion("second"),
        ]
    )

    await provider.complete(LLMRequest(system="s", user="u", max_tokens=600))
    await provider.complete(LLMRequest(system="s", user="u", max_tokens=600))

    assert len(calls) == 3
    assert calls[2]["max_tokens"] == calls[1]["max_tokens"] > calls[0]["max_tokens"]


async def test_a_short_answer_that_stopped_normally_is_not_retried() -> None:
    """Only the empty-and-truncated signature triggers a retry, not brevity."""
    provider, calls = _openai_provider_with([_chat_completion("Yes.", reasoning=400)])

    response = await provider.complete(LLMRequest(system="s", user="u", max_tokens=600))

    assert response.content == "Yes."
    assert len(calls) == 1


async def test_a_non_reasoning_truncation_is_not_retried() -> None:
    """Truncated with no reasoning spend is a real budget problem, not headroom.

    Retrying it would double the cost of every genuinely over-long generation.
    """
    provider, calls = _openai_provider_with(
        [_chat_completion("", finish_reason="length", reasoning=0)]
    )

    response = await provider.complete(LLMRequest(system="s", user="u", max_tokens=600))

    assert response.content == ""
    assert len(calls) == 1


def test_registry_returns_claude_provider(mock_async_client) -> None:
    config = LLMConfig(provider="claude", api_key="test-key")
    provider = get_provider(config)
    assert provider.name() == "claude"


def test_registry_routes_tasks_to_their_model_tier(mock_async_client) -> None:
    config = LLMConfig(provider="claude", api_key="test-key")
    assert get_provider(config, task="scoring").model == config.scoring_model
    assert get_provider(config, task="tailoring").model == config.tailoring_model
    assert get_provider(config, task="reasoning").model == config.reasoning_model
    assert get_provider(config, task=None).model == config.model


def test_resolve_model_falls_back_for_unknown_task() -> None:
    config = LLMConfig(provider="claude", model="fallback-model")
    assert resolve_model(config, task="does-not-exist") == "fallback-model"
    assert resolve_model(config) == "fallback-model"


def test_default_models_are_current() -> None:
    """Guards against a retired ID silently becoming the default again."""
    config = LLMConfig()
    for model in (
        config.model,
        config.scoring_model,
        config.tailoring_model,
        config.reasoning_model,
    ):
        assert not model.startswith("claude-sonnet-4-2025"), f"{model} is retired"
        assert "-2025" not in model, f"{model} pins a dated snapshot"


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


def test_claude_provider_name(mock_async_client) -> None:
    assert ClaudeProvider(api_key="test").name() == "claude"


def test_claude_supports_json_mode(mock_async_client) -> None:
    assert ClaudeProvider(api_key="test").supports_json_mode() is True


def test_openai_alias_is_compatible_provider() -> None:
    assert OpenAIProvider is OpenAICompatibleProvider
