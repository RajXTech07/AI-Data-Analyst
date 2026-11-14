import json
from typing import Any
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.agent.llm.base import LLMClient, LLMResponse
from app.core.config import settings
from app.core.errors import LLMProviderError
from app.core.logging import logger
from app.schemas.tool import ToolCall

class GeminiClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize GeminiClient")
        self.model = model or settings.LLM_MODEL
        self.client = genai.Client(api_key=self.api_key)

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.2
    ) -> LLMResponse:
        system_instruction = None
        contents: list[str] = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                contents.append(f"{role.capitalize()}: {content}")

        combined_prompt = "\n\n".join(contents)

        # Build config
        config_args: dict[str, Any] = {
            "temperature": temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        # Structured schema output
        if response_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = response_schema

        # Function calling tools
        if tools and not response_schema:
            function_declarations = []
            for t in tools:
                try:
                    params = t.get("parameters")
                    if isinstance(params, dict) and "$defs" in params:
                        # Dereference any leftover $defs/$ref
                        import copy
                        p_copy = copy.deepcopy(params)
                        defs = p_copy.pop("$defs", {})
                        def resolve(node):
                            if isinstance(node, dict):
                                if "$ref" in node:
                                    r_name = str(node["$ref"]).split("/")[-1]
                                    if r_name in defs:
                                        return resolve(defs[r_name])
                                return {k: resolve(v) for k, v in node.items()}
                            elif isinstance(node, list):
                                return [resolve(item) for item in node]
                            return node
                        params = resolve(p_copy)

                    function_declarations.append(
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t["description"],
                            parameters=params
                        )
                    )
                except Exception as fd_err:
                    logger.warning(f"Could not register tool '{t.get('name')}' for Gemini: {fd_err}")

            if function_declarations:
                config_args["tools"] = [types.Tool(function_declarations=function_declarations)]

        config = types.GenerateContentConfig(**config_args)

        import time
        max_retries = 2
        response = None
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=combined_prompt,
                    config=config
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("503" in err_str or "unavailable" in err_str or "429" in err_str or "resource_exhausted" in err_str) and attempt < max_retries - 1:
                    logger.warning(f"Gemini API transient error (attempt {attempt + 1}/{max_retries}), retrying in 1s: {e}")
                    time.sleep(1.0)
                    continue
                logger.error(f"Gemini API call failed: {str(e)}")
                raise LLMProviderError(f"Gemini generation error: {str(e)}")

        tool_calls: list[ToolCall] = []
        if getattr(response, "function_calls", None):
            for fc in response.function_calls:
                args_dict = dict(fc.args) if fc.args else {}
                tool_calls.append(ToolCall(name=fc.name, arguments=args_dict))

        # Parse structured data if requested
        structured_data = None
        text_content = response.text if hasattr(response, "text") else None
        if response_schema and text_content:
            try:
                data_dict = json.loads(text_content)
                structured_data = response_schema.model_validate(data_dict)
            except Exception as e:
                logger.warning(f"Could not parse response as {response_schema.__name__}: {str(e)}")

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            structured_data=structured_data,
            raw_response=response
        )
