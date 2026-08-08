"""
LLM service for OpenAI API calls
"""
import json
import logging
import os
from typing import List, Tuple, Optional

from openai import OpenAI

from app.prompts import TRANSCRIPT_WRITER_PROMPT, TRANSCRIPT_REWRITER_PROMPT

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# JSON Schema for the structured output used by optimize_transcript(). Passed to the
# Responses API via `text.format` so the model is constrained to return exactly this
# shape instead of us having to scrape a list literal out of free-form text.
TRANSCRIPT_SEGMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["Speaker 1", "Speaker 2"]},
                    "text": {"type": "string"},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}


class LLMService:
    """Service for interacting with OpenAI LLM"""

    def __init__(self):
        """Initialize OpenAI client"""
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
        Both generate_initial_transcript() and its continuation retry funnel through
        this so the request-building logic (including the gpt-5 temperature carve-out)
        lives in exactly one place.

        Args:
            instructions: System/developer instructions (the Responses API's
                equivalent of a system message).
            input_text: The user-facing prompt content.
            max_output_tokens: Upper bound on generated tokens.
            temperature: Sampling temperature; ignored for gpt-5* models, which don't
                support a custom value.

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

    def generate_initial_transcript(self, text_content: str, podcast_length_mode: str = "MEDIUM") -> str:
        """
        Generate initial podcast transcript from text content

        Args:
            text_content: Input text content
            podcast_length_mode: Podcast length mode (SHORT | MEDIUM | LONG)

        Returns:
            Initial transcript as string
        """
        # Replace {SHORT | MEDIUM | LONG} in prompt with actual mode
        prompt_template = TRANSCRIPT_WRITER_PROMPT.replace(
            "{SHORT | MEDIUM | LONG}",
            podcast_length_mode.upper()
        )
        prompt = f"{prompt_template}\n\nContent to convert:\n{text_content}"

        # Calculate max_output_tokens based on podcast length mode
        # Chinese characters typically require ~2 tokens per character
        # Add significant buffer to ensure we can reach target word count
        # Note: Need extra tokens for formatting, dialogue markers, and natural language overhead
        token_limits = {
            "SHORT": 5000,    # For 1,500-1,800 chars: ~3,000-3,600 tokens, buffer to 5000
            "MEDIUM": 12000,  # For 3,000-3,500 chars: ~6,000-7,000 tokens, buffer to 12000 (almost 2x)
            "LONG": 20000     # For 6,000-7,000 chars: ~12,000-14,000 tokens, buffer to 20000
        }
        max_tokens = token_limits.get(podcast_length_mode.upper(), 12000)

        try:
            transcript = self._generate_text(
                instructions="You are a world-class podcast writer.",
                input_text=prompt,
                max_output_tokens=max_tokens,
                temperature=0.8,
            )

            # Check word count and retry if insufficient
            word_count = len(transcript)
            min_word_counts = {
                "SHORT": 1500,
                "MEDIUM": 3000,
                "LONG": 6000
            }
            min_words = min_word_counts.get(podcast_length_mode.upper(), 3000)

            # If word count is insufficient, try to extend the transcript
            if word_count < min_words:
                logger.warning(
                    "Generated transcript has %d words, target is %d. Attempting to extend...",
                    word_count, min_words
                )

                # Create a continuation prompt
                continuation_prompt = f"""The previous transcript has only {word_count} words, but the target is {min_words} words for {podcast_length_mode.upper()} mode.

Please continue the conversation naturally. Add more:
- Detailed explanations and examples
- More interactions between speakers
- Additional questions and follow-ups
- More anecdotes and analogies
- Natural reactions and interruptions

Continue from where the transcript left off. Do NOT repeat what was already said. Just continue the conversation naturally until you reach at least {min_words} total words.

Previous transcript:
{transcript}

Continue the conversation:"""

                try:
                    continuation = self._generate_text(
                        instructions="You are a world-class podcast writer.",
                        input_text=continuation_prompt,
                        max_output_tokens=max_tokens // 2,  # Use half tokens for continuation
                        temperature=0.8,
                    )

                    # Append continuation to original transcript
                    transcript = f"{transcript}\n\n{continuation}"
                    logger.info("Extended transcript to %d words", len(transcript))
                except Exception as ext_error:
                    logger.warning("Failed to extend transcript: %s", ext_error)
                    # Return original transcript even if short

            return transcript

        except Exception as e:
            raise Exception(f"Failed to generate initial transcript: {str(e)}") from e

    def optimize_transcript(self, initial_transcript: str) -> List[Tuple[str, str]]:
        """
        Optimize transcript for TTS pipeline

        Uses OpenAI structured outputs (a json_schema response format) so the model
        is constrained to return {"segments": [{"speaker": ..., "text": ...}, ...]}
        instead of free-form text that has to be scraped for a `[...]` list literal.

        Args:
            initial_transcript: Initial transcript text

        Returns:
            List of tuples: [("Speaker 1", "text"), ("Speaker 2", "text"), ...]
        """
        prompt = f"{TRANSCRIPT_REWRITER_PROMPT}\n\nTranscript to optimize:\n{initial_transcript}"

        # Estimate required tokens based on input length
        # The optimized output may be similar or slightly longer than input
        # Chinese characters typically require ~2 tokens per character
        input_length = len(initial_transcript)
        estimated_output_tokens = int(input_length * 2.2)  # Add 10% buffer for markers and formatting

        # Set reasonable limits: minimum 4000, maximum 16000 (for LONG mode)
        max_tokens = max(4000, min(estimated_output_tokens, 16000))

        try:
            request_params = {
                "model": self.model,
                "instructions": "You are an international oscar winning screenwriter.",
                "input": prompt,
                "max_output_tokens": max_tokens,
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
                request_params["temperature"] = 0.7

            response = self.client.responses.create(**request_params)
            raw_output = response.output_text

            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError as parse_error:
                raise ValueError(f"Model did not return valid JSON: {parse_error}") from parse_error

            segments = data.get("segments") if isinstance(data, dict) else None
            if not isinstance(segments, list) or not segments:
                raise ValueError(f"Response JSON is missing a non-empty 'segments' list: {data!r}")

            transcript: List[Tuple[str, str]] = []
            for i, item in enumerate(segments):
                if not isinstance(item, dict) or "speaker" not in item or "text" not in item:
                    raise ValueError(f"Segment {i} has an invalid format: {item!r}")
                transcript.append((str(item["speaker"]), str(item["text"])))

            return transcript

        except Exception as e:
            raise Exception(f"Failed to optimize transcript: {str(e)}") from e


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
