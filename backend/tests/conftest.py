"""
Shared fixtures for the backend test suite.

Design goals (see the task brief this suite was written against):
  - No test may touch the developer's real backend/outputs/ directory.
  - No test may depend on execution order or leak state (env vars, singletons,
    rate-limit counters) into another test.
  - No test may require real Google Cloud / LLM credentials -- the TTS client
    and the LLM SDKs are always mocked. ffmpeg is real (it's installed in this
    environment) and merges are exercised for real rather than mocked.
"""
import importlib
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    # Belt-and-suspenders alongside pytest.ini's `pythonpath = .` -- makes this
    # conftest robust even if invoked in a way that skips ini processing.
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Env var isolation
# ---------------------------------------------------------------------------
# Every env var any module under test reads, at import time or call time.
# Cleared before every test so no test can see (or leak into another test)
# whatever happens to be set in the real environment / a real .env file.
_ISOLATED_ENV_VARS = [
    "LLM_PROVIDER",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY", "OPENAI_MODEL",
    "TTS_MODEL",
    "API_KEY", "RATE_LIMIT_WINDOW_SECONDS", "RATE_LIMIT_MAX_REQUESTS",
    "CORS_ALLOW_ORIGINS",
    "TASK_TTL_SECONDS", "TASK_MAX_COUNT",
    "SSE_STREAM_TIMEOUT_SECONDS", "SSE_KEEPALIVE_INTERVAL_SECONDS",
]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Strip provider/credential/config env vars before every test."""
    for var in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


# ---------------------------------------------------------------------------
# Singleton resets
# ---------------------------------------------------------------------------
# get_task_manager()/get_audio_service()/get_llm_service()/get_transcript_service()
# each cache a module-level singleton. Left alone, task state (and cached LLM
# clients built against a previous test's monkeypatched env) would leak between
# tests that happen to run in the same process. Reset before AND after each
# test so failures mid-test don't poison the next one either.
@pytest.fixture(autouse=True)
def reset_singletons():
    import app.services.task_manager as task_manager_module
    import app.services.audio_service as audio_service_module
    import app.services.llm.factory as llm_factory_module
    import app.services.transcript_service as transcript_service_module

    def _reset():
        task_manager_module._task_manager = None
        audio_service_module._audio_service = None
        llm_factory_module._llm_service = None
        transcript_service_module._transcript_service = None

    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# Filesystem isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolated_outputs_dir(tmp_path, monkeypatch):
    """
    Redirect every module-level OUTPUTS_DIR constant to a per-test tmp_path so
    nothing under test ever creates, reads, or deletes anything under the real
    backend/outputs/. Applied to every test (cheap, and it's the one thing we
    absolutely cannot get wrong).
    """
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    import app.services.task_manager as task_manager_module
    import app.api.routes as routes_module

    monkeypatch.setattr(task_manager_module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(routes_module, "OUTPUTS_DIR", outputs)
    return outputs


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """
    routes._rate_limit_hits is a module-level dict of per-IP sliding windows.
    Starlette's TestClient always presents the same client host ("testclient"),
    so without a reset, rate-limit hits from an earlier test would count
    against a later test's requests.
    """
    import app.api.routes as routes_module
    routes_module._rate_limit_hits.clear()
    yield
    routes_module._rate_limit_hits.clear()


# ---------------------------------------------------------------------------
# Real audio, via real ffmpeg (never mocked)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def real_short_mp3_bytes(tmp_path_factory) -> bytes:
    """A real ~1.0s silent mp3, rendered once via ffmpeg, reused by every test."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available on PATH")
    out_dir = tmp_path_factory.mktemp("fixture_audio")
    out_file = out_dir / "segment.mp3"
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "1.0",
            "-c:a", "libmp3lame", "-q:a", "2",
            str(out_file),
        ],
        capture_output=True, text=True, shell=False,
    )
    if result.returncode != 0:
        pytest.fail(f"failed to render fixture audio via ffmpeg: {result.stderr}")
    return out_file.read_bytes()


def ffprobe_duration_seconds(path: Path) -> float:
    """Real ffprobe duration lookup, used to assert merged output length."""
    ffprobe = shutil.which("ffprobe")
    assert ffprobe, "ffprobe not available on PATH"
    result = subprocess.run(
        [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, shell=False,
    )
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
    return float(result.stdout.strip())


@pytest.fixture
def mock_tts(monkeypatch, real_short_mp3_bytes):
    """
    Replace app.services.audio_service.get_client() with a fake Google Cloud TTS
    client so no test ever needs real credentials.

    - Every synthesis call is recorded (thread-safe -- generate_audio_from_transcript
      fans calls out across a ThreadPoolExecutor) with the text/prompt/voice/
      language/model it was called with, so tests can assert routing.
    - Segments whose text contains the marker "FAIL_ME" raise a *non-retryable*
      error (message contains "invalid", one of audio_service.is_retryable_error's
      non-retryable keywords) so failure tests run instantly instead of sleeping
      through generate_single_audio's retry/backoff loop.
    - Successful calls return the real short mp3 fixture as audio_content, so
      downstream ffmpeg merges are exercised against real audio bytes.

    Returns the shared `calls` list (each entry a dict) for assertions.
    """
    import app.services.audio_service as audio_service_module

    calls = []
    lock = threading.Lock()

    def fake_synthesize_speech(input, voice, audio_config):
        with lock:
            calls.append({
                "text": input.text,
                "prompt": getattr(input, "prompt", None),
                "voice_name": voice.name,
                "language_code": voice.language_code,
                "model_name": voice.model_name,
            })
        if "FAIL_ME" in input.text:
            raise ValueError("invalid input: simulated synthesis failure")
        response = MagicMock()
        response.audio_content = real_short_mp3_bytes
        return response

    fake_client = MagicMock()
    fake_client.synthesize_speech.side_effect = fake_synthesize_speech
    monkeypatch.setattr(audio_service_module, "get_client", lambda: fake_client)
    return calls


# ---------------------------------------------------------------------------
# HTTP test client
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    """
    TestClient bound to the *current* app.main.app. Imported at fixture-call
    time (not module import time) so it always reflects whatever app.main
    currently holds -- important because the CORS tests reload app.main, and
    they restore it to its default state on teardown (see test_routes.py).
    """
    from fastapi.testclient import TestClient
    import app.main as main_module
    return TestClient(main_module.app)


@pytest.fixture
def reloaded_main_app(monkeypatch):
    """
    Reload app.main with a given CORS_ALLOW_ORIGINS so its module-level
    CORS middleware config (computed once, at import time) reflects it.
    Restores app.main to its default (no CORS_ALLOW_ORIGINS override) state
    on teardown so later tests using the `client` fixture aren't affected.
    """
    import app.main as main_module

    def _reload(cors_origins: str):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", cors_origins)
        importlib.reload(main_module)
        return main_module.app

    yield _reload

    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    importlib.reload(main_module)
