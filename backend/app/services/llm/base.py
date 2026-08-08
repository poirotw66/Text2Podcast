"""
Provider-agnostic LLM service interface plus the request-orchestration logic
shared by every provider.

`BaseLLMService` implements the two public methods declared by
`LLMServiceInterface` (the transcript continuation-retry loop, the per-mode
token/word-count tables, and JSON segment parsing) exactly once, so
`GeminiLLMService` and `OpenAILLMService` can't drift from each other on
anything but the actual wire call to their own SDK. Each concrete provider
only implements two small hooks:

- `_generate_text()`          -- plain-text generation (used by
                                  generate_initial_transcript()).
- `_generate_json_segments()` -- structured JSON generation constrained to
                                  TRANSCRIPT_SEGMENTS_SCHEMA (used by
                                  optimize_transcript()).
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

from app.prompts import TRANSCRIPT_REWRITER_PROMPT, TRANSCRIPT_WRITER_PROMPT

logger = logging.getLogger(__name__)

# JSON Schema for the structured output used by optimize_transcript(). Shared
# verbatim by every provider -- OpenAI gets it via the Responses API's
# `text.format.schema` (json_schema mode), Gemini gets it via
# GenerateContentConfig.response_json_schema -- so the model is constrained to
# return exactly {"segments": [{"speaker": ..., "text": ...}, ...]} instead of
# us having to scrape a list literal out of free-form text.
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

# Podcast-length-mode tuning tables, shared by every provider so their
# behaviour can't diverge on how much to ask for / how much is "enough".
#
# Chinese characters typically require ~2 tokens per character. Buffers are
# generous to ensure we can reach the target word count plus formatting,
# dialogue markers, and natural-language overhead.
TOKEN_LIMITS = {
    "SHORT": 5000,    # For 1,500-1,800 chars: ~3,000-3,600 tokens, buffer to 5000
    "MEDIUM": 12000,  # For 3,000-3,500 chars: ~6,000-7,000 tokens, buffer to 12000 (almost 2x)
    "LONG": 20000,    # For 6,000-7,000 chars: ~12,000-14,000 tokens, buffer to 20000
}
MIN_WORD_COUNTS = {
    "SHORT": 1500,
    "MEDIUM": 3000,
    "LONG": 6000,
}


def parse_segments_json(raw_output: str) -> List[Tuple[str, str]]:
    """
    Parse a {"segments": [{"speaker": ..., "text": ...}, ...]} JSON payload
    (matching TRANSCRIPT_SEGMENTS_SCHEMA) into (speaker, text) tuples.

    Shared by every provider's optimize_transcript() so the parsing/validation
    rules -- and the resulting List[Tuple[str, str]] shape the rest of the app
    depends on -- can't drift between providers.
    """
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


class LLMServiceInterface(ABC):
    """Provider-agnostic interface consumed by transcript_service.py and routes.py."""

    @abstractmethod
    def generate_initial_transcript(self, text_content: str, podcast_length_mode: str = "MEDIUM") -> str:
        """
        Generate initial podcast transcript from text content.

        Args:
            text_content: Input text content
            podcast_length_mode: Podcast length mode (SHORT | MEDIUM | LONG)

        Returns:
            Initial transcript as string
        """
        raise NotImplementedError

    @abstractmethod
    def optimize_transcript(self, initial_transcript: str) -> List[Tuple[str, str]]:
        """
        Optimize transcript for the TTS pipeline.

        Args:
            initial_transcript: Initial transcript text

        Returns:
            List of tuples: [("Speaker 1", "text"), ("Speaker 2", "text"), ...]
        """
        raise NotImplementedError


class BaseLLMService(LLMServiceInterface):
    """
    Shared orchestration for both providers: prompt assembly, token-limit
    lookup, the short-transcript continuation retry, and JSON segment
    parsing/validation. Subclasses provide only the actual SDK calls.
    """

    # -- Hooks each concrete provider must implement ------------------------

    def _generate_text(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.8,
    ) -> str:
        """Plain-text generation against the provider's SDK. Returns stripped text."""
        raise NotImplementedError

    def _generate_json_segments(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        temperature: float = 0.7,
    ) -> str:
        """
        Structured generation constrained to TRANSCRIPT_SEGMENTS_SCHEMA against
        the provider's SDK. Returns the raw JSON text (not yet parsed).
        """
        raise NotImplementedError

    # -- Shared public API ---------------------------------------------------

    def generate_initial_transcript(self, text_content: str, podcast_length_mode: str = "MEDIUM") -> str:
        mode = podcast_length_mode.upper()

        # Replace {SHORT | MEDIUM | LONG} in prompt with actual mode
        prompt_template = TRANSCRIPT_WRITER_PROMPT.replace("{SHORT | MEDIUM | LONG}", mode)
        prompt = f"{prompt_template}\n\nContent to convert:\n{text_content}"

        max_tokens = TOKEN_LIMITS.get(mode, TOKEN_LIMITS["MEDIUM"])

        try:
            transcript = self._generate_text(
                instructions="You are a world-class podcast writer.",
                input_text=prompt,
                max_output_tokens=max_tokens,
                temperature=0.8,
            )

            # Check word count and retry if insufficient
            word_count = len(transcript)
            min_words = MIN_WORD_COUNTS.get(mode, MIN_WORD_COUNTS["MEDIUM"])

            # If word count is insufficient, try to extend the transcript
            if word_count < min_words:
                logger.warning(
                    "Generated transcript has %d words, target is %d. Attempting to extend...",
                    word_count, min_words
                )

                # Create a continuation prompt
                continuation_prompt = f"""The previous transcript has only {word_count} words, but the target is {min_words} words for {mode} mode.

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
        prompt = f"{TRANSCRIPT_REWRITER_PROMPT}\n\nTranscript to optimize:\n{initial_transcript}"

        # Estimate required tokens based on input length. The optimized output
        # may be similar or slightly longer than input. Chinese characters
        # typically require ~2 tokens per character.
        input_length = len(initial_transcript)
        estimated_output_tokens = int(input_length * 2.2)  # buffer for markers/formatting

        # Set reasonable limits: minimum 4000, maximum 16000 (for LONG mode)
        max_tokens = max(4000, min(estimated_output_tokens, 16000))

        try:
            raw_output = self._generate_json_segments(
                instructions="You are an international oscar winning screenwriter.",
                input_text=prompt,
                max_output_tokens=max_tokens,
                temperature=0.7,
            )
            return parse_segments_json(raw_output)

        except Exception as e:
            raise Exception(f"Failed to optimize transcript: {str(e)}") from e
