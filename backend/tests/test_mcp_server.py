"""
Tests for app/mcp_server.py, the local stdio MCP server.

Two styles of test here, deliberately:

- Most tests call the `@server.tool()`-decorated functions directly as plain
  async functions (they stay ordinary callables -- the decorator registers
  them as a side effect and returns them unchanged). This is fast and lets
  Google Cloud TTS be mocked in-process via conftest.py's `mock_tts` fixture,
  same as every other backend test.

- `TestRealStdioClientSession` below is different on purpose: it launches
  `python -m app.mcp_server` as a genuine subprocess and drives it with a
  real `mcp.client` stdio session (initialize -> list_tools -> call_tool),
  because a server that only *imports* cleanly is not proven to actually
  speak MCP -- and because progress notifications only exist on a live
  request/session, so they can't be observed via the direct-call style above
  (Context.report_progress requires a real ServerRequestContext, which the
  direct-call style never constructs). TTS is mocked across the process
  boundary via a `sitecustomize.py` dropped on the subprocess's PYTHONPATH,
  the same technique test_synthesize_skill.py uses for the same reason.
"""
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import pytest

import app.mcp_server as mcp_server
from app.services import pipeline

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
VOICE_LIST_PATH = REPO_ROOT / "voice_list.md"


def _segment(speaker: str, text: str) -> mcp_server.Segment:
    return mcp_server.Segment(speaker=speaker, text=text)


@pytest.fixture(autouse=True)
def dummy_google_credentials(monkeypatch, tmp_path_factory):
    """
    conftest.py's autouse `isolated_env` fixture strips GOOGLE_APPLICATION_CREDENTIALS
    from every test's environment (so no test accidentally depends on real
    credentials); check_prerequisites() would then fail its credentials check
    for every in-process test in this module unless something in this module
    puts a (dummy, unvalidated -- it's never actually sent anywhere, `mock_tts`
    replaces the client itself) credentials file back. Tests that specifically
    want to exercise the "no credentials" path unset this again explicitly.
    """
    cred_file = tmp_path_factory.mktemp("mcp_creds") / "fake-service-account.json"
    cred_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))


# ---------------------------------------------------------------------------
# Tool registration / schemas
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_tool_registration_and_schemas():
    tools = await mcp_server.server.list_tools()
    tools_by_name = {t.name: t for t in tools}

    assert set(tools_by_name) == {"list_voices", "synthesize_podcast", "regenerate_segment"}

    list_voices_schema = tools_by_name["list_voices"].input_schema
    assert list_voices_schema["properties"] == {}

    synth_schema = tools_by_name["synthesize_podcast"].input_schema
    assert set(synth_schema["required"]) == {"segments", "output_path"}
    assert "voices" in synth_schema["properties"]
    assert "styles" in synth_schema["properties"]
    assert "model" in synth_schema["properties"]
    assert "language" in synth_schema["properties"]
    # ctx: Context is injected by the framework, not part of the client-facing schema.
    assert "ctx" not in synth_schema["properties"]

    regen_schema = tools_by_name["regenerate_segment"].input_schema
    assert set(regen_schema["required"]) == {"output_path", "segment_index"}
    assert "ctx" not in regen_schema["properties"]


# ---------------------------------------------------------------------------
# list_voices
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_list_voices_matches_voice_list_md():
    voices = await mcp_server.list_voices()

    # Independently parse voice_list.md (tab-separated, one header row) and
    # compare -- this is the thing the design doc requires: list_voices must
    # not duplicate the table into code, it must read the file live.
    lines = VOICE_LIST_PATH.read_text(encoding="utf-8").splitlines()
    expected = []
    for line in lines[1:]:
        parts = line.split("\t")
        name = parts[0].strip()
        if not name:
            continue
        expected.append((name, parts[1].strip() if len(parts) > 1 else ""))

    assert len(voices) == 30
    assert [(v.name, v.gender) for v in voices] == expected
    assert all(v.gender in ("女性", "男性") for v in voices)


# ---------------------------------------------------------------------------
# synthesize_podcast
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_synthesize_podcast_success(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"

    result = await mcp_server.synthesize_podcast(
        segments=[_segment("Speaker 1", "hello"), _segment("Speaker 2", "hi back")],
        output_path=str(output),
        ctx=None,
    )

    assert result.output_path == str(output)
    assert output.exists()
    assert result.total_segments == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.partial is False
    assert result.failed_segments == []
    assert result.duration_seconds is not None and result.duration_seconds > 0
    assert "all succeeded" in result.message.lower()

    # Working files were kept alongside the output (not cleaned up like the CLI does).
    segments_dir = Path(result.segments_dir)
    assert segments_dir == output.with_name("podcast.segments")
    assert (segments_dir / "metadata.json").exists()

    assert len(mock_tts) == 2
    assert {c["text"] for c in mock_tts} == {"hello", "hi back"}


@pytest.mark.anyio
async def test_synthesize_podcast_partial_failure_reports_failed_indices(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"

    result = await mcp_server.synthesize_podcast(
        segments=[
            _segment("Speaker 1", "hello"),
            _segment("Speaker 2", "FAIL_ME oops"),
            _segment("Speaker 1", "still here"),
        ],
        output_path=str(output),
        ctx=None,
    )

    # Partial failure must be loud: output still exists (it's missing only the
    # failed line), but is unambiguously flagged, and names exactly which
    # segment failed -- not just a bare failure count.
    assert output.exists()
    assert result.partial is True
    assert result.succeeded == 2
    assert result.failed == 1
    assert result.total_segments == 3
    assert len(result.failed_segments) == 1
    assert result.failed_segments[0].index == 2
    assert result.failed_segments[0].speaker == "Speaker 2"
    assert "invalid" in result.failed_segments[0].error.lower()
    assert "warning" in result.message.lower()
    assert "1 of 3" in result.message


@pytest.mark.anyio
async def test_synthesize_podcast_all_segments_failed_raises_tool_error(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"

    with pytest.raises(mcp_server.ToolError) as exc_info:
        await mcp_server.synthesize_podcast(
            segments=[_segment("Speaker 1", "FAIL_ME a"), _segment("Speaker 2", "FAIL_ME b")],
            output_path=str(output),
            ctx=None,
        )

    assert not output.exists()
    message = str(exc_info.value)
    assert "failed to synthesize" in message.lower()
    assert "segment 1" in message
    assert "segment 2" in message


@pytest.mark.anyio
async def test_synthesize_podcast_style_length_cap_rejected(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"
    too_long = "x" * (pipeline.MAX_STYLE_PROMPT_LENGTH + 1)

    with pytest.raises(ValueError, match=r"exceeds 200 characters"):
        await mcp_server.synthesize_podcast(
            segments=[_segment("Speaker 1", "hello")],
            output_path=str(output),
            styles={"Speaker 1": too_long},
            ctx=None,
        )

    assert not output.exists()
    assert len(mock_tts) == 0  # rejected before any TTS call was made


@pytest.mark.anyio
async def test_synthesize_podcast_requires_absolute_output_path(mock_tts):
    with pytest.raises(ValueError, match="absolute"):
        await mcp_server.synthesize_podcast(
            segments=[_segment("Speaker 1", "hello")],
            output_path="relative/podcast.mp3",
            ctx=None,
        )
    assert len(mock_tts) == 0


@pytest.mark.anyio
async def test_synthesize_podcast_rejects_empty_segments(tmp_path, mock_tts):
    with pytest.raises(ValueError, match="non-empty"):
        await mcp_server.synthesize_podcast(
            segments=[], output_path=str(tmp_path / "out.mp3"), ctx=None,
        )


@pytest.mark.anyio
async def test_synthesize_podcast_preflight_failure_becomes_tool_error(tmp_path, monkeypatch, mock_tts):
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    with pytest.raises(Exception) as exc_info:
        await mcp_server.synthesize_podcast(
            segments=[_segment("Speaker 1", "hello")],
            output_path=str(tmp_path / "out.mp3"),
            ctx=None,
        )

    assert "ffmpeg" in str(exc_info.value).lower()
    assert len(mock_tts) == 0  # never got past the preflight check


@pytest.mark.anyio
async def test_synthesize_podcast_voice_and_style_overrides_reach_tts_call(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"

    await mcp_server.synthesize_podcast(
        segments=[_segment("Speaker 1", "hello"), _segment("Speaker 2", "hi")],
        output_path=str(output),
        voices={"Speaker 1": "Puck"},
        styles={"Speaker 1": "Speak like a pirate"},
        model="custom-model-x",
        language="en-GB",
        ctx=None,
    )

    calls = {c["text"]: c for c in mock_tts}
    assert calls["hello"]["voice_name"] == "Puck"
    assert calls["hello"]["prompt"] == "Speak like a pirate"
    assert calls["hello"]["model_name"] == "custom-model-x"
    assert calls["hello"]["language_code"] == "en-GB"
    # Speaker 2 wasn't overridden -- must fall back to the module default, not "Kore".
    assert calls["hi"]["voice_name"] == "Charon"


# ---------------------------------------------------------------------------
# regenerate_segment
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_regenerate_segment_repairs_episode(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"

    synth_result = await mcp_server.synthesize_podcast(
        segments=[_segment("Speaker 1", "original one"), _segment("Speaker 2", "FAIL_ME broken")],
        output_path=str(output),
        ctx=None,
    )
    assert synth_result.partial is True
    assert synth_result.failed == 1
    mock_tts.clear()

    regen_result = await mcp_server.regenerate_segment(
        output_path=str(output),
        segment_index=2,
        text="fixed now",
        voice="Puck",
        ctx=None,
    )

    assert regen_result.regenerated_success is True
    assert regen_result.regenerated_error is None
    assert regen_result.failed == 0
    assert regen_result.succeeded == 2
    assert regen_result.partial is False
    assert "regenerated successfully" in regen_result.message.lower()

    assert len(mock_tts) == 1
    assert mock_tts[0]["text"] == "fixed now"
    assert mock_tts[0]["voice_name"] == "Puck"

    # metadata.json reflects the fix.
    metadata_file = pipeline.metadata_file_for(output)
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    entry = next(e for e in metadata["audio_files"] if e["index"] == 2)
    assert entry["text"] == "fixed now"
    assert entry["success"] is True


@pytest.mark.anyio
async def test_regenerate_segment_missing_working_files_error(tmp_path, mock_tts):
    output = tmp_path / "never_synthesized.mp3"

    with pytest.raises(Exception) as exc_info:
        await mcp_server.regenerate_segment(output_path=str(output), segment_index=1, ctx=None)

    message = str(exc_info.value)
    assert "no working files found" in message.lower()
    assert str(output) in message
    assert len(mock_tts) == 0


@pytest.mark.anyio
async def test_regenerate_segment_requires_absolute_output_path(mock_tts):
    with pytest.raises(ValueError, match="absolute"):
        await mcp_server.regenerate_segment(output_path="relative.mp3", segment_index=1, ctx=None)


@pytest.mark.anyio
async def test_regenerate_segment_style_prompt_length_cap(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"
    await mcp_server.synthesize_podcast(
        segments=[_segment("Speaker 1", "hello")], output_path=str(output), ctx=None,
    )
    mock_tts.clear()

    too_long = "x" * (pipeline.MAX_STYLE_PROMPT_LENGTH + 1)
    with pytest.raises(ValueError, match=r"exceeds 200 characters"):
        await mcp_server.regenerate_segment(
            output_path=str(output), segment_index=1, style_prompt=too_long, ctx=None,
        )
    assert len(mock_tts) == 0


@pytest.mark.anyio
async def test_regenerate_segment_unknown_index_raises(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"
    await mcp_server.synthesize_podcast(
        segments=[_segment("Speaker 1", "hello")], output_path=str(output), ctx=None,
    )
    mock_tts.clear()

    with pytest.raises(Exception, match="not found in metadata"):
        await mcp_server.regenerate_segment(output_path=str(output), segment_index=99, ctx=None)


# ---------------------------------------------------------------------------
# call_tool() end-to-end (still in-process, but through the real MCP dispatch
# path rather than calling the python function directly).
#
# Note: `MCPServer.call_tool()` (the plain Python API used here) re-raises a
# tool body's exception as `ToolError` rather than returning a non-raising
# `is_error` result -- that conversion only happens one layer up, in the
# wire-facing `_handle_call_tool()` (verified by reading
# mcp/server/mcpserver/tools/base.py and confirmed empirically below).
# `TestRealStdioClientSession` below goes through that real wire path and
# asserts the non-raising `is_error` behavior a genuine client sees.
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_call_tool_reports_errors_as_tool_error(tmp_path, mock_tts):
    with pytest.raises(mcp_server.ToolError, match="non-empty"):
        await mcp_server.server.call_tool(
            "synthesize_podcast",
            {"segments": [], "output_path": str(tmp_path / "out.mp3")},
        )


@pytest.mark.anyio
async def test_call_tool_success_has_structured_content(tmp_path, mock_tts):
    output = tmp_path / "podcast.mp3"
    result = await mcp_server.server.call_tool(
        "synthesize_podcast",
        {
            "segments": [{"speaker": "Speaker 1", "text": "hello"}],
            "output_path": str(output),
        },
    )
    assert not result.is_error
    assert result.structured_content["succeeded"] == 1
    assert result.structured_content["output_path"] == str(output)


# ---------------------------------------------------------------------------
# Real stdio client session -- genuine subprocess, genuine mcp.client session.
# ---------------------------------------------------------------------------
_SITECUSTOMIZE_TEMPLATE = '''\
import base64
import json
import threading
from unittest.mock import MagicMock

_AUDIO_BYTES = base64.b64decode("__AUDIO_B64__")
_LOCK = threading.Lock()


class _FakeTTSClient:
    def synthesize_speech(self, input, voice, audio_config):
        if "FAIL_ME" in input.text:
            raise ValueError("invalid input: simulated synthesis failure")
        resp = MagicMock()
        resp.audio_content = _AUDIO_BYTES
        return resp


import google.cloud.texttospeech as _tts  # noqa: E402
_tts.TextToSpeechClient = lambda *a, **k: _FakeTTSClient()
'''


def _write_tts_mock_sitecustomize(dir_path: Path, audio_bytes: bytes) -> None:
    content = _SITECUSTOMIZE_TEMPLATE.replace(
        "__AUDIO_B64__", base64.b64encode(audio_bytes).decode("ascii")
    )
    (dir_path / "sitecustomize.py").write_text(content, encoding="utf-8")


def _dummy_credentials_file(tmp_path: Path) -> Path:
    p = tmp_path / "fake-service-account.json"
    p.write_text("{}", encoding="utf-8")
    return p


class TestRealStdioClientSession:
    """
    Launches `python -m app.mcp_server` as a real subprocess and drives it
    with mcp.client over stdio: initialize, list_tools, call_tool. Proves the
    server actually completes an MCP handshake and a full tool call -- not
    just that the module imports.
    """

    @pytest.mark.anyio
    async def test_initialize_list_tools_and_synthesize_end_to_end(self, tmp_path, real_short_mp3_bytes):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        mock_dir = tmp_path / "mock"
        mock_dir.mkdir()
        _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

        output = tmp_path / "podcast.mp3"

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(mock_dir), str(BACKEND_DIR), env.get("PYTHONPATH", "")])
        env["GOOGLE_APPLICATION_CREDENTIALS"] = str(_dummy_credentials_file(tmp_path))
        for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "TTS_MODEL"):
            env.pop(var, None)

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            cwd=str(BACKEND_DIR),
            env=env,
        )

        progress_events = []

        async def on_progress(progress: float, total: Optional[float], message: Optional[str]) -> None:
            progress_events.append((progress, total, message))

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                assert init_result.server_info.name == "text2podcast"

                tools_result = await session.list_tools()
                tool_names = {t.name for t in tools_result.tools}
                assert tool_names == {"list_voices", "synthesize_podcast", "regenerate_segment"}

                voices_result = await session.call_tool("list_voices", {})
                assert not voices_result.is_error
                assert len(voices_result.structured_content["result"]) == 30

                synth_result = await session.call_tool(
                    "synthesize_podcast",
                    {
                        "segments": [
                            {"speaker": "Speaker 1", "text": "hello there"},
                            {"speaker": "Speaker 2", "text": "hi right back"},
                            {"speaker": "Speaker 1", "text": "one more line"},
                        ],
                        "output_path": str(output),
                    },
                    progress_callback=on_progress,
                )

        assert not synth_result.is_error, synth_result.content
        structured = synth_result.structured_content
        assert structured["succeeded"] == 3
        assert structured["failed"] == 0
        assert structured["output_path"] == str(output)

        # A real merged MP3 landed at the requested path -- not base64 in the
        # tool result, an actual file on disk (per the design doc's "files,
        # not blobs" requirement).
        assert output.exists()
        assert output.stat().st_size > 0

        # Progress notifications were genuinely emitted over the wire during
        # the multi-segment synthesis, not just a single before/after report.
        assert len(progress_events) >= 3
        for progress, total, message in progress_events:
            assert total == 3
            assert message  # each carries a human-readable "segment N/3 (...)" note

    @pytest.mark.anyio
    async def test_missing_credentials_surfaces_as_tool_error_over_the_wire(self, tmp_path, real_short_mp3_bytes):
        """
        No GOOGLE_APPLICATION_CREDENTIALS and no ambient ADC -> check_prerequisites()
        must turn into an is_error tool result, not a crashed server or a raw
        traceback leaking over the transport.
        """
        import google.auth
        try:
            google.auth.default()
        except Exception:
            pass
        else:
            pytest.skip("ambient Application Default Credentials are present in this environment")

        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        mock_dir = tmp_path / "mock"
        mock_dir.mkdir()
        _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(mock_dir), str(BACKEND_DIR), env.get("PYTHONPATH", "")])
        for var in ("GOOGLE_APPLICATION_CREDENTIALS", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
            env.pop(var, None)

        server_params = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND_DIR), env=env,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "synthesize_podcast",
                    {
                        "segments": [{"speaker": "Speaker 1", "text": "hello"}],
                        "output_path": str(tmp_path / "out.mp3"),
                    },
                )

        assert result.is_error is True
        assert "credential" in result.content[0].text.lower()
