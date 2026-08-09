"""
Tests for app.services.llm.gemini_service.GeminiLLMService: credential
resolution order, and that the actual generate_content request carries the
right model/system_instruction/response_mime_type/response_json_schema --
and specifically does NOT set response_schema (see the module's own docstring
for why response_json_schema was chosen deliberately).
"""
from unittest.mock import MagicMock

import pytest
from google.genai import types

from app.services.llm.base import TRANSCRIPT_SEGMENTS_SCHEMA
from app.services.llm.gemini_service import DEFAULT_GEMINI_MODEL, GeminiLLMService


def _mock_genai_client(monkeypatch):
    import app.services.llm.gemini_service as gemini_module
    client_cls = MagicMock()
    fake_client = MagicMock()
    client_cls.return_value = fake_client
    monkeypatch.setattr(gemini_module.genai, "Client", client_cls)
    return client_cls, fake_client


# ---------------------------------------------------------------------------
# Credential resolution order
# ---------------------------------------------------------------------------

def test_uses_gemini_api_key_when_present(monkeypatch):
    client_cls, _ = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gk-123")

    GeminiLLMService()

    client_cls.assert_called_once_with(api_key="gk-123")


def test_falls_back_to_google_api_key(monkeypatch):
    client_cls, _ = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "gk-fallback")

    GeminiLLMService()

    client_cls.assert_called_once_with(api_key="gk-fallback")


def test_gemini_api_key_takes_priority_over_google_api_key(monkeypatch):
    client_cls, _ = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "primary")
    monkeypatch.setenv("GOOGLE_API_KEY", "secondary")

    GeminiLLMService()

    client_cls.assert_called_once_with(api_key="primary")


def test_falls_back_to_vertex_via_project_when_no_api_key(monkeypatch):
    client_cls, _ = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")

    GeminiLLMService()

    client_cls.assert_called_once_with(vertexai=True, project="my-project", location="global")


def test_vertex_location_is_configurable(monkeypatch):
    client_cls, _ = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    GeminiLLMService()

    client_cls.assert_called_once_with(vertexai=True, project="my-project", location="us-central1")


def test_no_credentials_raises_clear_actionable_error(monkeypatch):
    _mock_genai_client(monkeypatch)
    with pytest.raises(ValueError, match="No Gemini credentials found"):
        GeminiLLMService()


def test_model_env_var_overrides_default(monkeypatch):
    _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gk-123")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")

    service = GeminiLLMService()
    assert service.model == "gemini-custom"


def test_model_defaults_when_env_unset(monkeypatch):
    _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gk-123")

    service = GeminiLLMService()
    assert service.model == DEFAULT_GEMINI_MODEL


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------

def _build_service(monkeypatch):
    _, fake_client = _mock_genai_client(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gk-123")
    service = GeminiLLMService()
    fake_client.models.generate_content.return_value = MagicMock(text="response text")
    return service, fake_client


def test_generate_json_segments_request_shape(monkeypatch):
    service, fake_client = _build_service(monkeypatch)

    service._generate_json_segments(
        instructions="be a screenwriter", input_text="optimize this",
        max_output_tokens=1234, temperature=0.5,
    )

    fake_client.models.generate_content.assert_called_once()
    call_kwargs = fake_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == service.model
    assert call_kwargs["contents"] == "optimize this"

    config = call_kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction == "be a screenwriter"
    assert config.max_output_tokens == 1234
    assert config.temperature == 0.5
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == TRANSCRIPT_SEGMENTS_SCHEMA
    # The deliberate choice this module documents: response_json_schema, not
    # response_schema (which would silently drop additionalProperties/enum).
    assert config.response_schema is None


def test_generate_text_request_shape_has_no_json_fields(monkeypatch):
    service, fake_client = _build_service(monkeypatch)

    service._generate_text(
        instructions="be a podcast writer", input_text="write this",
        max_output_tokens=999, temperature=0.9,
    )

    call_kwargs = fake_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    assert config.system_instruction == "be a podcast writer"
    assert config.max_output_tokens == 999
    assert config.temperature == 0.9
    assert config.response_mime_type is None
    assert config.response_json_schema is None
    assert config.response_schema is None


def test_generate_text_returns_stripped_response_text(monkeypatch):
    service, fake_client = _build_service(monkeypatch)
    fake_client.models.generate_content.return_value = MagicMock(text="  padded text  \n")

    result = service._generate_text("sys", "input", 100)
    assert result == "padded text"


def test_generate_text_handles_none_response_text(monkeypatch):
    service, fake_client = _build_service(monkeypatch)
    fake_client.models.generate_content.return_value = MagicMock(text=None)

    result = service._generate_text("sys", "input", 100)
    assert result == ""
