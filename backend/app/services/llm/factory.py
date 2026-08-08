"""
Provider selection and singleton for LLMServiceInterface.
"""
import os
from typing import Optional

from app.services.llm.base import LLMServiceInterface
from app.services.llm.gemini_service import GeminiLLMService
from app.services.llm.openai_service import OpenAILLMService

_PROVIDERS = {
    "gemini": GeminiLLMService,
    "openai": OpenAILLMService,
}

# Singleton instance
_llm_service: Optional[LLMServiceInterface] = None


def get_llm_service() -> LLMServiceInterface:
    """
    Get or create the singleton LLM service instance.

    Selected via the LLM_PROVIDER env var ("gemini" | "openai"), defaulting to
    "gemini" so the app can run on Google credentials alone (the TTS side is
    already Google). Set LLM_PROVIDER=openai (with OPENAI_API_KEY) to use the
    original OpenAI-backed script writer instead.
    """
    global _llm_service
    if _llm_service is None:
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        try:
            provider_cls = _PROVIDERS[provider]
        except KeyError:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{provider}'. Supported values: "
                f"{', '.join(sorted(_PROVIDERS))}."
            ) from None
        _llm_service = provider_cls()
    return _llm_service
