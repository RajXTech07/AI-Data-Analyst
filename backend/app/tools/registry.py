from dataclasses import dataclass
import time
from typing import Any, Callable, get_type_hints
import pandas as pd
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import ToolArgumentError
from app.core.logging import logger
from app.schemas.tool import ToolResult
from app.tools.base import sanitize_for_json

@dataclass
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any, pd.DataFrame], ToolResult]

REGISTRY: dict[str, ToolSpec] = {}

def tool(name: str, description: str):
    """Decorator to register a pure analysis tool function."""
    def decorator(fn: Callable[[Any, pd.DataFrame], ToolResult]):
        hints = get_type_hints(fn)
        args_model = hints.get("args")
        if not args_model or not issubclass(args_model, BaseModel):
            raise TypeError(f"Tool function '{fn.__name__}' must specify an 'args' parameter annotated with a BaseModel subclass.")
        REGISTRY[name] = ToolSpec(name=name, description=description, args_model=args_model, fn=fn)
        return fn
    return decorator

def get_tool(name: str) -> ToolSpec | None:
    return REGISTRY.get(name)

def list_tools() -> list[ToolSpec]:
    return list(REGISTRY.values())

def _inline_dereference_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inlines all $defs/$ref in a JSON Schema so it is compatible with OpenAPI 3.0 / LLM tools."""
    import copy
    schema_copy = copy.deepcopy(schema)
    defs = schema_copy.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_path = str(node["$ref"])
                ref_name = ref_path.split("/")[-1]
                if ref_name in defs:
                    return resolve(defs[ref_name])
            return {k: resolve(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema_copy)

def llm_tool_schemas() -> list[dict[str, Any]]:
    """Converts the registry into JSON Schema definitions for LLM function calling."""
    schemas: list[dict[str, Any]] = []
    for spec in REGISTRY.values():
        param_schema = spec.args_model.model_json_schema()
        # Clean up titles and inline $defs for OpenAPI 3.0 / Gemini function declaration compatibility
        param_schema.pop("title", None)
        clean_schema = _inline_dereference_schema(param_schema)
        schemas.append({
            "name": spec.name,
            "description": spec.description,
            "parameters": clean_schema,
        })
    return schemas

def run_tool(name: str, raw_args: dict[str, Any], df: pd.DataFrame) -> ToolResult:
    """Validates parameters and executes the registered pure tool."""
    spec = REGISTRY.get(name)
    if not spec:
        return ToolResult(
            ok=False,
            error=f"Unknown tool '{name}'. Available tools: {list(REGISTRY.keys())}"
        )

    start_time = time.perf_counter()
    try:
        # Validate arguments through Pydantic
        args = spec.args_model.model_validate(raw_args)
    except ValidationError as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return ToolResult(
            ok=False,
            error=f"Invalid arguments for tool '{name}': {str(e)}",
            duration_ms=duration_ms
        )

    try:
        # Pure function execution
        result = spec.fn(args, df)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        result.duration_ms = duration_ms
        result.data = sanitize_for_json(result.data)
        return result

    except ToolArgumentError as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.warning(f"ToolArgumentError in {name}: {e.message}")
        return ToolResult(
            ok=False,
            error=e.message,
            duration_ms=duration_ms
        )
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"Unexpected error in tool {name}: {str(e)}", exc_info=True)
        return ToolResult(
            ok=False,
            error=f"Execution error in {name}: {str(e)}",
            duration_ms=duration_ms
        )
