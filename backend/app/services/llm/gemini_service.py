"""
Gemini implementation of LLMServiceInterface, using the `google-genai` SDK
(2.x -- NOT the deprecated `google-generativeai` package).

Credentials resolve in this order:
1. GEMINI_API_KEY (or GOOGLE_API_KEY) -- Gemini Developer API, via
   genai.Client(api_key=...).
2. Vertex AI via Application Default Credentials, using GOOGLE_CLOUD_PROJECT
   (+ optional GOOGLE_CLOUD_LOCATION, default "global") -- this project
   already requires GOOGLE_APPLICATION_CREDENTIALS for Cloud TTS, so this
   path needs no new credentials of its own.
3. Neither present -> raise a clear, actionable error naming the env vars.
"""
import logging
import os

from google import genai
from google.genai import types

from app.services.llm.base import TRANSCRIPT_SEGMENTS_SCHEMA, BaseLLMService

logger = logging.getLogger(__name__)

# Single, well-named place to change the Gemini model used for transcript
# generation/optimization -- deliberately not scattered across the class.
# NOTE: not verified against a live API in this environment (no credentials
# available in this sandbox). The Cloud TTS side already targets the
# gemini-2.5-* family (see audio_service.TTS_MODEL), so gemini-2.5-flash was
# chosen as the fast, general-purpose text model in that same family.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiLLMService(BaseLLMService):
    """LLM service backed by Gemini via the google-genai SDK."""

    def __init__(self):
        """Initialize the google-genai client (API key or Vertex AI, see module docstring)."""
        self.client = self._build_client()
        self.model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    @staticmethod
    def _build_client() -> genai.Client:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            return genai.Client(api_key=api_key)

        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        if project:
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
            # Vertex AI via ADC (GOOGLE_APPLICATION_CREDENTIALS) -- no API key needed.
            return genai.Client(vertexai=True, project=project, location=location)

        raise ValueError(
            "No Gemini credentials found. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
            "to use the Gemini Developer API, or set GOOGLE_CLOUD_PROJECT "
            "(with GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account "
            "key, as already required for Cloud TTS) to use Vertex AI instead."
        )

    def _generate_text(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.8,
    ) -> str:
        """
        Plain-text generation via client.models.generate_content(). Gemini has
        no "temperature unsupported" carve-out like gpt-5* does -- that quirk
        is OpenAI-specific and stays confined to OpenAILLMService.

        Returns:
            The generated text (response.text), stripped. Note: response.parsed
            does not exist on GenerateContentResponse in google-genai 2.17.0,
            so callers must not rely on it.
        """
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=input_text,
            config=config,
        )
        return (response.text or "").strip()

    def _generate_json_segments(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.7,
    ) -> str:
        """
        Structured-output generation constrained to TRANSCRIPT_SEGMENTS_SCHEMA.

        Uses `response_json_schema` rather than `response_schema`: the schema
        already relies on `additionalProperties: False` (to forbid stray keys)
        and a plain string `enum` on "speaker", and google-genai's docstring
        for GenerateContentConfig documents `response_json_schema` as the field
        that supports `additionalProperties` and `enum` for a plain JSON
        Schema dict passed through largely as-is. `response_schema` instead
        converts the dict into Gemini's own OpenAPI-3.0-derived `Schema` type,
        which is documented as a "select subset" and is not confirmed to carry
        `additionalProperties` through -- so `response_json_schema` is the
        better match for reusing TRANSCRIPT_SEGMENTS_SCHEMA verbatim, matching
        how the schema is already shared unmodified with the OpenAI path.

        Returns:
            The raw JSON text (response.text), not yet parsed.
        """
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_json_schema=TRANSCRIPT_SEGMENTS_SCHEMA,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=input_text,
            config=config,
        )
        return response.text
