from typing import Any, Literal
from pydantic import BaseModel, Field

class Event(BaseModel):
    event: Literal[
        "status",
        "plan",
        "tool_started",
        "tool_finished",
        "hypothesis",
        "finding",
        "chart",
        "message_delta",
        "error",
        "done",
    ]
    data: dict[str, Any] = Field(default_factory=dict)
