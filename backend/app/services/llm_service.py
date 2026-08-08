"""
LLM service -- provider-pluggable (Gemini default, OpenAI selectable via
LLM_PROVIDER=openai).

This module is kept as the stable import site
(`from app.services.llm_service import get_llm_service`) used by
transcript_service.py and app/api/routes.py. The actual interface and
implementations live in app/services/llm/:

- llm/base.py           LLMServiceInterface, BaseLLMService (shared retry /
                         token-limit / JSON-parsing logic), TRANSCRIPT_SEGMENTS_SCHEMA.
- llm/gemini_service.py  GeminiLLMService -- the default, via google-genai.
- llm/openai_service.py  OpenAILLMService -- the original implementation.
- llm/factory.py         get_llm_service() -- singleton, selected by LLM_PROVIDER.
"""
# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.llm.base import LLMServiceInterface, TRANSCRIPT_SEGMENTS_SCHEMA
from app.services.llm.factory import get_llm_service
from app.services.llm.gemini_service import GeminiLLMService
from app.services.llm.openai_service import OpenAILLMService

__all__ = [
    "get_llm_service",
    "LLMServiceInterface",
    "TRANSCRIPT_SEGMENTS_SCHEMA",
    "GeminiLLMService",
    "OpenAILLMService",
]
