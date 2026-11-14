import os
from app.agent.llm.base import LLMClient, LLMResponse
from app.agent.llm.gemini import GeminiClient
from app.agent.llm.mock import MockLLMClient
from app.core.config import settings
from app.core.logging import logger

def get_llm_client(force_mock: bool = False) -> LLMClient:
    """Returns the configured LLM client or MockLLMClient if no API key is available."""
    if force_mock:
        return MockLLMClient()

    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        logger.info(f"Using GeminiClient with model '{settings.LLM_MODEL}'")
        return GeminiClient(api_key=api_key)
    
    logger.info("No GEMINI_API_KEY configured. Falling back to MockLLMClient.")
    return MockLLMClient()

__all__ = ["LLMClient", "LLMResponse", "GeminiClient", "MockLLMClient", "get_llm_client"]
