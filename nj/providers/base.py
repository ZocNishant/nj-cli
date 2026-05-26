from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class LLMRequest(BaseModel):
    system: str
    user: str
    max_tokens: int = 1000
    temperature: float = 0.2
    response_format: Literal["text", "json"] = "json"


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
