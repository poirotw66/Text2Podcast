# Podcast Generation Backend

FastAPI backend for generating podcasts from text content.

## AI providers: two separate jobs, two separate configs

This backend calls out to two different AI services for two different
pipeline steps -- don't conflate them:

- **Script writing** (Step 1 `generate_initial_transcript`, Step 2
  `optimize_transcript`) -- `app/services/llm/`. **Pluggable**, selected by
  `LLM_PROVIDER`:
  - `gemini` (**default**) -- `GeminiLLMService`, via the `google-genai` SDK.
    Needs `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), or falls back to Vertex AI
    using `GOOGLE_CLOUD_PROJECT` + the same `GOOGLE_APPLICATION_CREDENTIALS`
    service account already required for TTS below.
  - `openai` -- `OpenAILLMService`, the original implementation, unchanged.
    Needs `OPENAI_API_KEY`. Not read at all unless `LLM_PROVIDER=openai`.
- **Text-to-speech** (Step 3, `app/services/audio_service.py`) -- **always**
  Google Cloud TTS (`gemini-2.5-flash-tts`). Not affected by `LLM_PROVIDER`,
  not configurable to any other provider. Needs
  `GOOGLE_APPLICATION_CREDENTIALS`.

So with the default configuration (`LLM_PROVIDER` unset, i.e. `gemini`), the
whole backend runs on Google credentials alone -- no OpenAI key is read or
required anywhere. See `.env.example` at the repo root for the full variable
list, and `app/services/llm/base.py` / `gemini_service.py` / `openai_service.py`
/ `factory.py` for the implementation.

## ⚠️ Deployment constraint: single process only

`TaskManager` (`app/services/task_manager.py`) keeps all task state in an
**in-memory dict inside one Python process**. It is not shared across
processes, so:

- **Run this API with a single worker.** `uvicorn app.main:app --workers 2`
  (or any multi-process deployment — multiple `gunicorn` workers, multiple
  container replicas behind a naive load balancer, etc.) will silently break
  it: a request can land on a worker process that never created (or never
  updated) the task it's asking about, so `/api/status/{task_id}`,
  `/api/stream/{task_id}`, and the step endpoints will intermittently 404 or
  show stale progress depending on which process handles the request.
- This also means task state does not survive a process restart.

If you need multiple workers or processes, `TaskManager` must first be
swapped for a shared backend (Redis, SQLite, etc.). To make that swap
mechanical, `app/services/task_manager.py` defines a small `TaskStore`
abstract interface capturing every operation the rest of the app depends on
(`create_task`, `get_task`, `update_task_status`, `set_task_error`,
`set_task_files`). A future `RedisTaskStore` / `SQLiteTaskStore` implementing
that same interface can be dropped in via `get_task_manager()` without
touching any call site. No such backend is implemented here — this is
scaffolding for that future work, not a promise it already scales.

`TaskManager` also evicts old tasks on its own (TTL-based, plus a hard cap on
task count, both lazily on access — see `TASK_TTL_SECONDS` / `TASK_MAX_COUNT`
below) and cleans up each task's `outputs/<task_id>/` directory when it does,
so the process doesn't leak memory or disk indefinitely on a long-running
server.

## Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

Every direct dependency is pinned to an exact version in `requirements.txt`
(there's no separate lockfile tool wired up for this project). `ffmpeg` must
also be installed and on `PATH` — it's invoked directly via `subprocess` to
merge audio segments (see `app/services/audio_service.py`); it's no longer
pulled in transitively through `pydub`, which has been removed.

2. Set environment variables — see [`.env.example`](../.env.example) at the
   repo root for the full list with descriptions. The essentials (default
   provider, Gemini -- see "AI providers" above):

```bash
export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
export GEMINI_API_KEY=your_gemini_api_key
```

Or create a `.env` file in the backend directory (loaded automatically via
`python-dotenv`):
```
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
GEMINI_API_KEY=your_gemini_api_key
```

To use OpenAI for script writing instead (TTS stays Google either way):
```
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
```

Notable optional variables (all documented in `.env.example`):

- `LLM_PROVIDER` — `gemini` (default) or `openai`; selects the script-writing
  implementation (`app/services/llm/factory.py`).
- `GEMINI_MODEL` — defaults to `gemini-2.5-flash`. `GOOGLE_CLOUD_PROJECT` /
  `GOOGLE_CLOUD_LOCATION` configure the Vertex AI fallback used when no
  `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set.
- `OPENAI_MODEL` — defaults to `gpt-5-mini`. Only relevant when
  `LLM_PROVIDER=openai`.
- `CORS_ALLOW_ORIGINS` — comma-separated allowed origins; defaults to the two
  local dev frontends. `allow_credentials` is only enabled when this isn't a
  wildcard, since browsers reject that combination outright.
- `API_KEY` — if set, `/api/upload`, `/api/step1/{id}`, `/api/step2`, and
  `/api/step3/{id}` require a matching `X-API-Key` header. Unset by default
  (open, for local dev). `/health` is never gated.
- `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_MAX_REQUESTS` — simple in-process
  per-client-IP rate limiting on the same endpoints as `API_KEY`.
- `TASK_TTL_SECONDS` / `TASK_MAX_COUNT` — TaskManager eviction tuning (see
  above).
- `SSE_STREAM_TIMEOUT_SECONDS` / `SSE_KEEPALIVE_INTERVAL_SECONDS` — bound how
  long an `/api/stream/{task_id}` connection can stay open and how often it
  sends a keep-alive comment while idle.

## Running

Start the server (single worker — see the constraint above):
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## API Endpoints

- `POST /api/upload` - Upload text content and create a task (Step 0)
- `POST /api/step1/{task_id}` - Step 1: generate the initial transcript
- `POST /api/step2` - Step 2: optimize the transcript for TTS
- `POST /api/step3/{task_id}` - Step 3: generate audio from the final transcript
- `GET /api/status/{task_id}` - Get task status
- `GET /api/download/{task_id}/audio` - Download audio file
- `GET /api/download/{task_id}/transcript` - Download transcript file
- `GET /api/transcript/{task_id}` - Get the transcript content as JSON
- `GET /api/stream/{task_id}` - SSE stream for progress updates

`upload`, `step1`, `step2`, and `step3` require an `X-API-Key` header if
`API_KEY` is configured, and are subject to per-IP rate limiting — see above.
