# Adding an LLM Provider

## Interface

All providers extend `BaseLLMProvider`:

```python
from nj.providers.base import (
    BaseLLMProvider, LLMRequest, LLMResponse
)

class MyProvider(BaseLLMProvider):
    def name(self) -> str:
        return "myprovider"

    def supports_json_mode(self) -> bool:
        return True  # or False

    async def complete(
        self, request: LLMRequest
    ) -> LLMResponse:
        ...
```

## LLMRequest fields
- `system: str` — system prompt
- `user: str` — user message
- `max_tokens: int` — default 1000
- `temperature: float` — default 0.2
- `response_format: "text" | "json"` — hint only

## LLMResponse fields
- `content: str` — response text
- `provider: str` — your provider name
- `model: str` — model used
- `input_tokens: int`
- `output_tokens: int`
- `latency_ms: int`

## Registering your provider

Add to `nj/providers/registry.py` get_provider():
```python
if provider_name == "myprovider":
    from nj.providers.myprovider import MyProvider
    return MyProvider(api_key=config.api_key)
```

Add config fields to `LLMConfig` if needed.

## Important notes

- JSON mode: if `supports_json_mode()` is False, the scoring
  and tailoring prompts still work — they instruct the model
  to return JSON via the prompt text
- Temperature: respect `request.temperature` — don't hardcode
- Latency: record with `time.monotonic()` before/after call
- Errors: let exceptions propagate — scorer.py handles retries
