"""
OpenAI implementation of LLMServiceInterface.

This is the original LLMService's behaviour (previously the only
implementation in llm_service.py), moved behind the provider-agnostic
interface with no functional change: same model default, same gpt-5*
temperature carve-out, same Responses API json_schema structured-output
request shape.
"""
import os

from openai import OpenAI

from app.services.llm.base import TRANSCRIPT_SEGMENTS_SCHEMA, BaseLLMService


class OpenAILLMService(BaseLLMService):
    """LLM service backed by OpenAI's Responses API."""

    def __init__(self):
        """Initialize OpenAI client. Requires OPENAI_API_KEY."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    def _generate_text(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.8,
    ) -> str:
        """
        Shared helper around client.responses.create() for plain-text generations.
        Both generate_initial_transcript() and its continuation retry funnel
        through this (via BaseLLMService) so the request-building logic
        (including the gpt-5 temperature carve-out) lives in exactly one place.

        Args:
            instructions: System/developer instructions (the Responses API's
                equivalent of a system message).
            input_text: The user-facing prompt content.
            max_output_tokens: Upper bound on generated tokens.
            temperature: Sampling temperature; ignored for gpt-5* models, which
                don't support a custom value.

        Returns:
            The generated text (response.output_text), stripped.
        """
        request_params = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
        }

        # gpt-5-mini (and other gpt-5* models) don't support a custom temperature.
        if not self.model.startswith("gpt-5"):
            request_params["temperature"] = temperature

        response = self.client.responses.create(**request_params)
        return response.output_text.strip()

    def _generate_json_segments(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.7,
    ) -> str:
        """
        Structured-output generation via the Responses API's json_schema
        text format, constrained to TRANSCRIPT_SEGMENTS_SCHEMA.

        Returns:
            The raw JSON text (response.output_text), not yet parsed.
        """
        request_params = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "podcast_segments",
                    "schema": TRANSCRIPT_SEGMENTS_SCHEMA,
                    "strict": True,
                }
            },
        }

        # Only add temperature if model supports it (gpt-5-mini doesn't support custom temperature)
        if not self.model.startswith("gpt-5"):
            request_params["temperature"] = temperature

        response = self.client.responses.create(**request_params)
        return response.output_text
