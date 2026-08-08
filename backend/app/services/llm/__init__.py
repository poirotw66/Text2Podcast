"""
Provider-pluggable LLM service package.

- base.py           Provider-agnostic interface (LLMServiceInterface), the shared
                     request-orchestration logic (BaseLLMService), the JSON segments
                     schema, and the token/word-count tuning tables.
- gemini_service.py  GeminiLLMService -- the default provider, via google-genai.
- openai_service.py  OpenAILLMService -- the original implementation, unchanged
                     behaviour, moved behind the interface.
- factory.py         get_llm_service() -- singleton selection by LLM_PROVIDER.

External code should keep importing from `app.services.llm_service`, which
re-exports everything here -- that stays the stable import site.
"""
