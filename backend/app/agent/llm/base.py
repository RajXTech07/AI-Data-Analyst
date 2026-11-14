from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel
from app.schemas.tool import ToolCall

@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    structured_data: Any | None = None
    raw_response: Any | None = None

@runtime_checkable
class LLMClient(Protocol):
    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.2
    ) -> LLMResponse:
        """Generates a completion from the LLM, optionally invoking tools or producing structured schema output."""
        ...
