from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class LLMRequest(BaseModel):
    system: str
    user: str
    max_tokens: int = 1000
    # Only honoured by providers that still accept sampling params. The Claude
    # 5-family models reject temperature/top_p/top_k with a 400, so the Claude
    # provider ignores this field.
    temperature: float = 0.2
    response_format: Literal["text", "json"] = "json"
    # When set, providers that support constrained decoding will guarantee the
    # response parses against this JSON Schema instead of us salvaging JSON out
    # of prose with fence-stripping heuristics.
    json_schema: dict | None = None
    # Marks the system prompt as a stable cache prefix. Worth setting whenever
    # the same system text is reused across many calls in one run (scoring).
    cache_system: bool = False


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports_json_mode(self) -> bool: ...
