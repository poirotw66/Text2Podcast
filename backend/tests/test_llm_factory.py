"""
Tests for app.services.llm.factory: provider selection via LLM_PROVIDER, and
that selecting Gemini (the default) never requires an OpenAI credential.
"""
from unittest.mock import MagicMock

import pytest

import app.services.llm.factory as factory_module
from app.services.llm.gemini_service import GeminiLLMService
from app.services.llm.openai_service import OpenAILLMService


def test_default_provider_is_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(GeminiLLMService, "_build_client", staticmethod(lambda: MagicMock()))

    service = factory_module.get_llm_service()
    assert isinstance(service, GeminiLLMService)


def test_explicit_openai_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")

    service = factory_module.get_llm_service()
    assert isinstance(service, OpenAILLMService)


def test_gemini_provider_selection_does_not_require_openai_key(monkeypatch):
    """Selecting gemini (the default) must succeed with only Gemini
    credentials present -- no OPENAI_API_KEY needed anywhere."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(GeminiLLMService, "_build_client", staticmethod(lambda: MagicMock()))

    service = factory_module.get_llm_service()
    assert isinstance(service, GeminiLLMService)


def test_unknown_provider_raises_clear_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER 'not-a-real-provider'"):
        factory_module.get_llm_service()


def test_provider_env_var_is_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "  OpenAI  ")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    service = factory_module.get_llm_service()
    assert isinstance(service, OpenAILLMService)


def test_get_llm_service_is_a_singleton(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    first = factory_module.get_llm_service()
    second = factory_module.get_llm_service()
    assert first is second
