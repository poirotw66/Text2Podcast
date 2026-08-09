"""
Full API contract tests via FastAPI's TestClient, with the TTS layer mocked
(via the `mock_tts` conftest fixture -- never real Google Cloud credentials).

Where a route needs a transcript to act on, tests pass `final_transcript`
directly to POST /api/step3/{task_id} rather than exercising the LLM-backed
step1/step2 endpoints (those are covered at the unit level in
test_llm_base.py / test_llm_gemini.py / test_llm_openai.py) -- this keeps the
route tests fast and independent of any LLM SDK.
"""
import json

from app.services.task_manager import get_task_manager

EXPECTED_PATHS = {
    "/", "/health",
    "/api/upload", "/api/step1/{task_id}", "/api/step2", "/api/step3/{task_id}",
    "/api/segments/{task_id}", "/api/regenerate/{task_id}", "/api/status/{task_id}",
    "/api/download/{task_id}/audio", "/api/download/{task_id}/transcript",
    "/api/transcript/{task_id}", "/api/stream/{task_id}",
}


def _create_task(client) -> str:
    resp = client.post("/api/upload", json={"text": "some source content"})
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


def _run_step3(client, task_id, transcript, **extra):
    return client.post(f"/api/step3/{task_id}", json={"final_transcript": transcript, **extra})


# ---------------------------------------------------------------------------
# Route table
# ---------------------------------------------------------------------------

def _iter_leaf_routes(routes):
    """
    Recursively walk an app's route table down to leaf Route/APIRoute objects.

    Newer FastAPI (0.141+) doesn't flatten an included APIRouter's routes into
    app.routes at include_router() time -- it wraps them in an internal
    `_IncludedRouter` whose actual routes live on `.original_router.routes`.
    Walk both that shape and a plain `.routes` attribute so this doesn't care
    which FastAPI/Starlette internal structure is in play.
    """
    for r in routes:
        if hasattr(r, "path"):
            yield r
        elif hasattr(r, "original_router"):
            yield from _iter_leaf_routes(r.original_router.routes)
        elif hasattr(r, "routes"):
            yield from _iter_leaf_routes(r.routes)


def test_all_13_documented_paths_exist(client):
    import app.main as main_module
    # FastAPI auto-adds /docs, /redoc, /openapi.json (and the oauth2 redirect
    # helper) -- exclude those; this test is about the application's own
    # route table, not FastAPI's built-in tooling.
    fastapi_builtin_paths = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
    paths = {
        r.path for r in _iter_leaf_routes(main_module.app.routes)
        if r.path not in fastapi_builtin_paths
    }
    assert paths == EXPECTED_PATHS
    assert len(EXPECTED_PATHS) == 13


# ---------------------------------------------------------------------------
# Happy path end to end
# ---------------------------------------------------------------------------

def test_full_pipeline_success_downloads_and_transcript(client, mock_tts):
    task_id = _create_task(client)
    transcript = [["Speaker 1", "hello there"], ["Speaker 2", "hi back"]]

    resp = _run_step3(client, task_id, transcript)
    assert resp.status_code == 200, resp.text

    status = client.get(f"/api/status/{task_id}").json()
    assert status["status"] == "completed"
    assert status["partial"] is False
    assert status["total_segments"] == 2
    assert status["failed_segments"] == 0
    assert status["message"] == "Podcast generation completed!"

    audio_resp = client.get(f"/api/download/{task_id}/audio")
    assert audio_resp.status_code == 200
    assert audio_resp.headers["content-type"] == "audio/mpeg"
    assert len(audio_resp.content) > 0

    transcript_resp = client.get(f"/api/download/{task_id}/transcript")
    assert transcript_resp.status_code == 200

    transcript_json = client.get(f"/api/transcript/{task_id}")
    assert transcript_json.status_code == 200
    assert transcript_json.json()["transcript"] == [["Speaker 1", "hello there"], ["Speaker 2", "hi back"]]


# ---------------------------------------------------------------------------
# Partial failure / all-fail
# ---------------------------------------------------------------------------

def test_step3_partial_failure_ends_completed_with_partial_flag(client, mock_tts):
    task_id = _create_task(client)
    transcript = [
        ["Speaker 1", "this works"],
        ["Speaker 2", "FAIL_ME this does not"],
        ["Speaker 1", "this works too"],
    ]

    resp = _run_step3(client, task_id, transcript)
    assert resp.status_code == 200, resp.text

    status = client.get(f"/api/status/{task_id}").json()
    assert status["status"] == "completed"
    assert status["partial"] is True
    assert status["total_segments"] == 3
    assert status["failed_segments"] == 1
    assert "1 of 3 segments failed" in status["message"]

    # Audio should still be produced despite the partial failure.
    audio_resp = client.get(f"/api/download/{task_id}/audio")
    assert audio_resp.status_code == 200


def test_step3_all_fail_ends_failed(client, mock_tts):
    task_id = _create_task(client)
    transcript = [["Speaker 1", "FAIL_ME a"], ["Speaker 2", "FAIL_ME b"]]

    resp = _run_step3(client, task_id, transcript)
    assert resp.status_code == 200, resp.text

    status = client.get(f"/api/status/{task_id}").json()
    assert status["status"] == "failed"
    assert status["error"] == "Failed to generate any audio files"


# ---------------------------------------------------------------------------
# GET /api/segments
# ---------------------------------------------------------------------------

def test_get_segments_lists_failed_segments(client, mock_tts):
    task_id = _create_task(client)
    transcript = [
        ["Speaker 1", "ok"],
        ["Speaker 2", "FAIL_ME bad"],
    ]
    _run_step3(client, task_id, transcript)

    resp = client.get(f"/api/segments/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["failed"] == 1
    segments = {s["index"]: s for s in body["segments"]}
    assert segments[1]["success"] is True
    assert segments[1]["error"] is None
    assert segments[2]["success"] is False
    assert segments[2]["error"] is not None


def test_get_segments_404_for_unknown_task(client):
    resp = client.get("/api/segments/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


def test_get_segments_404_when_audio_not_generated_yet(client):
    task_id = _create_task(client)
    resp = client.get(f"/api/segments/{task_id}")
    assert resp.status_code == 404
    assert "has not run" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/regenerate
# ---------------------------------------------------------------------------

def test_regenerate_fixes_segment_and_recomputes(client, mock_tts):
    task_id = _create_task(client)
    transcript = [
        ["Speaker 1", "ok"],
        ["Speaker 2", "FAIL_ME bad"],
    ]
    _run_step3(client, task_id, transcript)
    status = client.get(f"/api/status/{task_id}").json()
    assert status["partial"] is True

    resp = client.post(f"/api/regenerate/{task_id}", json={
        "segment_index": 2, "text": "now fixed", "voice": "Puck",
    })
    assert resp.status_code == 200, resp.text

    status = client.get(f"/api/status/{task_id}").json()
    assert status["status"] == "completed"
    assert status["partial"] is False
    assert status["failed_segments"] == 0

    segments = client.get(f"/api/segments/{task_id}").json()["segments"]
    fixed = next(s for s in segments if s["index"] == 2)
    assert fixed["success"] is True
    assert fixed["text"] == "now fixed"
    assert fixed["voice"] == "Puck"


def test_regenerate_out_of_range_index_returns_400(client, mock_tts):
    task_id = _create_task(client)
    _run_step3(client, task_id, [["Speaker 1", "a"], ["Speaker 2", "b"]])

    resp = client.post(f"/api/regenerate/{task_id}", json={"segment_index": 0})
    assert resp.status_code == 400

    resp = client.post(f"/api/regenerate/{task_id}", json={"segment_index": 99})
    assert resp.status_code == 400


def test_regenerate_over_long_style_prompt_returns_400(client, mock_tts):
    task_id = _create_task(client)
    _run_step3(client, task_id, [["Speaker 1", "a"], ["Speaker 2", "b"]])

    too_long = "x" * 201
    resp = client.post(f"/api/regenerate/{task_id}", json={
        "segment_index": 1, "style_prompt": too_long,
    })
    assert resp.status_code == 400
    assert "200 characters" in resp.json()["detail"]


def test_regenerate_404_when_no_audio_yet(client):
    task_id = _create_task(client)
    resp = client.post(f"/api/regenerate/{task_id}", json={"segment_index": 1})
    assert resp.status_code == 404


def test_step3_style_settings_over_long_returns_400(client, mock_tts):
    task_id = _create_task(client)
    resp = _run_step3(
        client, task_id, [["Speaker 1", "a"]],
        style_settings={"Speaker 1": "x" * 201},
    )
    assert resp.status_code == 400
    assert "200 characters" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Auth (X-API-Key)
# ---------------------------------------------------------------------------

def test_no_api_key_configured_allows_unauthenticated_requests(client):
    resp = client.post("/api/upload", json={"text": "hi"})
    assert resp.status_code == 200


def test_api_key_configured_rejects_missing_header(client, monkeypatch):
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "API_KEY", "secret123")

    resp = client.post("/api/upload", json={"text": "hi"})
    assert resp.status_code == 401


def test_api_key_configured_rejects_wrong_key(client, monkeypatch):
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "API_KEY", "secret123")

    resp = client.post("/api/upload", json={"text": "hi"}, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_api_key_configured_accepts_correct_key(client, monkeypatch):
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "API_KEY", "secret123")

    resp = client.post("/api/upload", json={"text": "hi"}, headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200


def test_health_endpoint_is_never_gated(client, monkeypatch):
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "API_KEY", "secret123")
    resp = client.get("/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_returns_429_once_exceeded(client, monkeypatch):
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "RATE_LIMIT_MAX_REQUESTS", 2)
    monkeypatch.setattr(routes_module, "RATE_LIMIT_WINDOW_SECONDS", 60.0)

    r1 = client.post("/api/upload", json={"text": "one"})
    r2 = client.post("/api/upload", json={"text": "two"})
    r3 = client.post("/api/upload", json={"text": "three"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_rate_limit_is_per_window_not_global(client, monkeypatch):
    """Sanity check that the limit only applies within RATE_LIMIT_WINDOW_SECONDS
    -- simulated by making the window effectively zero-length."""
    import app.api.routes as routes_module
    monkeypatch.setattr(routes_module, "RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(routes_module, "RATE_LIMIT_WINDOW_SECONDS", 0.0)

    r1 = client.post("/api/upload", json={"text": "one"})
    r2 = client.post("/api/upload", json={"text": "two"})
    assert r1.status_code == 200
    assert r2.status_code == 200  # window already elapsed by the time r2 arrives


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def test_cors_wildcard_origin_disables_credentials(reloaded_main_app):
    app = reloaded_main_app("*")
    cors_mw = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors_mw.kwargs["allow_origins"] == ["*"]
    assert cors_mw.kwargs["allow_credentials"] is False


def test_cors_explicit_origin_enables_credentials(reloaded_main_app):
    app = reloaded_main_app("https://example.com,https://app.example.com")
    cors_mw = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors_mw.kwargs["allow_origins"] == ["https://example.com", "https://app.example.com"]
    assert cors_mw.kwargs["allow_credentials"] is True


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------

def test_sse_stream_delivers_event_and_is_resubscribable(client):
    """
    A COMPLETED task's stream sends exactly one progress event and closes --
    this keeps the test deterministic (no reliance on disconnect-detection
    timing). The real thing under test is that a *second*, independent
    subscribe to the same task_id after the first stream has already run to
    completion still works cleanly.
    """
    from app.models.schemas import TaskStatus

    tm = get_task_manager()
    task_id = tm.create_task("hello")
    tm.update_task_status(task_id, TaskStatus.COMPLETED, progress=100, message="all done")

    with client.stream("GET", f"/api/stream/{task_id}") as resp1:
        assert resp1.status_code == 200
        body1 = "".join(resp1.iter_text())
    assert "event: progress" in body1
    assert '"status":"completed"' in body1
    assert '"message":"all done"' in body1

    # Re-subscribe after the first stream has fully closed.
    with client.stream("GET", f"/api/stream/{task_id}") as resp2:
        assert resp2.status_code == 200
        body2 = "".join(resp2.iter_text())
    assert "event: progress" in body2
    assert '"status":"completed"' in body2


def test_sse_stream_404_for_unknown_task(client):
    resp = client.get("/api/stream/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Status endpoint basics
# ---------------------------------------------------------------------------

def test_status_404_for_unknown_task(client):
    resp = client.get("/api/status/does-not-exist")
    assert resp.status_code == 404


def test_upload_rejects_empty_text(client):
    resp = client.post("/api/upload", json={"text": "   "})
    assert resp.status_code == 400


def test_download_audio_404_before_generation(client):
    task_id = _create_task(client)
    resp = client.get(f"/api/download/{task_id}/audio")
    assert resp.status_code == 404
