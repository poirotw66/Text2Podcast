"""
Tests for app.services.llm.base: the shared continuation-retry loop and the
shared JSON segment parser. Exercised against a minimal concrete subclass so
these tests can't accidentally depend on either real provider's SDK.
"""
import json

import pytest

from app.services.llm.base import (
    MIN_WORD_COUNTS, TOKEN_LIMITS, BaseLLMService, parse_segments_json,
)


class _RecordingLLMService(BaseLLMService):
    """A BaseLLMService subclass whose hooks are fully controlled by the test."""

    def __init__(self, text_responses=None, json_response=None):
        self._text_responses = list(text_responses or [])
        self._json_response = json_response
        self.text_calls = []
        self.json_calls = []

    def _generate_text(self, instructions, input_text, max_output_tokens, temperature=0.8):
        self.text_calls.append({
            "instructions": instructions, "input_text": input_text,
            "max_output_tokens": max_output_tokens, "temperature": temperature,
        })
        return self._text_responses.pop(0)

    def _generate_json_segments(self, instructions, input_text, max_output_tokens, temperature=0.7):
        self.json_calls.append({
            "instructions": instructions, "input_text": input_text,
            "max_output_tokens": max_output_tokens, "temperature": temperature,
        })
        return self._json_response


def test_generate_initial_transcript_no_retry_when_already_long_enough():
    long_enough = "x" * (MIN_WORD_COUNTS["SHORT"] + 100)
    service = _RecordingLLMService(text_responses=[long_enough])

    result = service.generate_initial_transcript("some content", podcast_length_mode="SHORT")

    assert result == long_enough
    assert len(service.text_calls) == 1  # continuation never fired


def test_generate_initial_transcript_continuation_retry_fires_once_with_half_tokens():
    mode = "SHORT"
    short_transcript = "x" * 10  # far under MIN_WORD_COUNTS["SHORT"]
    continuation = "y" * 50
    service = _RecordingLLMService(text_responses=[short_transcript, continuation])

    result = service.generate_initial_transcript("some content", podcast_length_mode=mode)

    assert len(service.text_calls) == 2  # fired exactly once
    first_call, second_call = service.text_calls
    assert first_call["max_output_tokens"] == TOKEN_LIMITS[mode]
    assert second_call["max_output_tokens"] == TOKEN_LIMITS[mode] // 2  # half the token budget
    assert result == f"{short_transcript}\n\n{continuation}"


def test_generate_initial_transcript_continuation_failure_returns_original():
    class _FailingContinuation(_RecordingLLMService):
        def _generate_text(self, instructions, input_text, max_output_tokens, temperature=0.8):
            self.text_calls.append(1)
            if len(self.text_calls) == 1:
                return "short"
            raise RuntimeError("continuation blew up")

    service = _FailingContinuation()
    result = service.generate_initial_transcript("content", podcast_length_mode="SHORT")
    assert result == "short"  # falls back to the original, short transcript
    assert len(service.text_calls) == 2  # continuation was attempted once


def test_generate_initial_transcript_mode_is_case_insensitive_and_defaults_medium():
    service = _RecordingLLMService(text_responses=["x" * (MIN_WORD_COUNTS["MEDIUM"] + 1)])
    service.generate_initial_transcript("content", podcast_length_mode="medium")
    assert service.text_calls[0]["max_output_tokens"] == TOKEN_LIMITS["MEDIUM"]


def test_generate_initial_transcript_wraps_hook_exception():
    class _Boom(_RecordingLLMService):
        def _generate_text(self, *a, **k):
            raise RuntimeError("sdk exploded")

    with pytest.raises(Exception, match="Failed to generate initial transcript"):
        _Boom().generate_initial_transcript("content")


def test_optimize_transcript_parses_segments():
    payload = json.dumps({"segments": [
        {"speaker": "Speaker 1", "text": "hi"},
        {"speaker": "Speaker 2", "text": "hello"},
    ]})
    service = _RecordingLLMService(json_response=payload)
    result = service.optimize_transcript("some initial transcript")
    assert result == [("Speaker 1", "hi"), ("Speaker 2", "hello")]
    assert len(service.json_calls) == 1


def test_optimize_transcript_wraps_hook_exception():
    class _Boom(_RecordingLLMService):
        def _generate_json_segments(self, *a, **k):
            raise RuntimeError("sdk exploded")

    with pytest.raises(Exception, match="Failed to optimize transcript"):
        _Boom().optimize_transcript("content")


# ---------------------------------------------------------------------------
# parse_segments_json
# ---------------------------------------------------------------------------

def test_parse_segments_json_happy_path():
    raw = json.dumps({"segments": [
        {"speaker": "Speaker 1", "text": "a"},
        {"speaker": "Speaker 2", "text": "b"},
    ]})
    assert parse_segments_json(raw) == [("Speaker 1", "a"), ("Speaker 2", "b")]


def test_parse_segments_json_coerces_non_string_values_to_str():
    raw = json.dumps({"segments": [{"speaker": "Speaker 1", "text": 123}]})
    assert parse_segments_json(raw) == [("Speaker 1", "123")]


def test_parse_segments_json_invalid_json_raises_value_error():
    with pytest.raises(ValueError, match="did not return valid JSON"):
        parse_segments_json("not json at all {{{")


def test_parse_segments_json_missing_segments_key_raises():
    with pytest.raises(ValueError, match="segments"):
        parse_segments_json(json.dumps({"oops": []}))


def test_parse_segments_json_empty_segments_list_raises():
    with pytest.raises(ValueError, match="segments"):
        parse_segments_json(json.dumps({"segments": []}))


def test_parse_segments_json_segment_missing_required_key_raises():
    with pytest.raises(ValueError, match="invalid format"):
        parse_segments_json(json.dumps({"segments": [{"speaker": "Speaker 1"}]}))


def test_parse_segments_json_top_level_not_a_dict_raises():
    with pytest.raises(ValueError):
        parse_segments_json(json.dumps(["not", "a", "dict"]))
