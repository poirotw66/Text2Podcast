"""
Tests for app.services.llm.openai_service.OpenAILLMService: the API-key
requirement, the gpt-5* temperature carve-out, and the Responses API request
shape for both plain-text and structured JSON generation.
"""
from unittest.mock import MagicMock

import pytest

from app.services.llm.base import TRANSCRIPT_SEGMENTS_SCHEMA
from app.services.llm.openai_service import OpenAILLMService


def _mock_openai_client(monkeypatch):
    import app.services.llm.openai_service as openai_module
    client_cls = MagicMock()
    fake_client = MagicMock()
    client_cls.return_value = fake_client
    monkeypatch.setattr(openai_module, "OpenAI", client_cls)
    return client_cls, fake_client


def test_missing_api_key_raises_value_error(monkeypatch):
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        OpenAILLMService()


def test_client_constructed_with_api_key(monkeypatch):
    client_cls, _ = _mock_openai_client(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    OpenAILLMService()

    client_cls.assert_called_once_with(api_key="sk-test-123")


def test_model_defaults_to_gpt5_mini(monkeypatch):
    _mock_openai_client(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    service = OpenAILLMService()
    assert service.model == "gpt-5-mini"


def test_model_env_var_overrides_default(monkeypatch):
    _mock_openai_client(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    service = OpenAILLMService()
    assert service.model == "gpt-4o"


def _build_service(monkeypatch, model=None):
    _, fake_client = _mock_openai_client(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    if model:
        monkeypatch.setenv("OPENAI_MODEL", model)
    service = OpenAILLMService()
    fake_client.responses.create.return_value = MagicMock(output_text="  response  \n")
    return service, fake_client


# ---------------------------------------------------------------------------
# gpt-5* temperature carve-out
# ---------------------------------------------------------------------------

def test_gpt5_model_omits_temperature_in_text_request(monkeypatch):
    service, fake_client = _build_service(monkeypatch, model="gpt-5-mini")
    service._generate_text("instructions", "input", 500, temperature=0.8)
    kwargs = fake_client.responses.create.call_args.kwargs
    assert "temperature" not in kwargs


def test_gpt5_model_omits_temperature_in_json_request(monkeypatch):
    service, fake_client = _build_service(monkeypatch, model="gpt-5-nano")
    service._generate_json_segments("instructions", "input", 500, temperature=0.7)
    kwargs = fake_client.responses.create.call_args.kwargs
    assert "temperature" not in kwargs


def test_non_gpt5_model_includes_temperature(monkeypatch):
    service, fake_client = _build_service(monkeypatch, model="gpt-4o")
    service._generate_text("instructions", "input", 500, temperature=0.33)
    kwargs = fake_client.responses.create.call_args.kwargs
    assert kwargs["temperature"] == 0.33


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------

def test_generate_text_request_shape(monkeypatch):
    service, fake_client = _build_service(monkeypatch, model="gpt-4o")
    result = service._generate_text("be helpful", "the prompt", 750, temperature=0.6)

    kwargs = fake_client.responses.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["instructions"] == "be helpful"
    assert kwargs["input"] == "the prompt"
    assert kwargs["max_output_tokens"] == 750
    assert kwargs["temperature"] == 0.6
    assert "text" not in kwargs  # plain text path has no structured-output config
    assert result == "response"  # stripped


def test_generate_json_segments_request_shape(monkeypatch):
    service, fake_client = _build_service(monkeypatch, model="gpt-4o")
    fake_client.responses.create.return_value = MagicMock(output_text='{"segments": []}')

    result = service._generate_json_segments("be a screenwriter", "optimize this", 900, temperature=0.4)

    kwargs = fake_client.responses.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["instructions"] == "be a screenwriter"
    assert kwargs["input"] == "optimize this"
    assert kwargs["max_output_tokens"] == 900
    assert kwargs["temperature"] == 0.4
    assert kwargs["text"]["format"]["type"] == "json_schema"
    assert kwargs["text"]["format"]["schema"] == TRANSCRIPT_SEGMENTS_SCHEMA
    assert kwargs["text"]["format"]["strict"] is True
    assert result == '{"segments": []}'  # NOT stripped -- caller (parse_segments_json) handles it
