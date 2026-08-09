"""
Tests for .claude/skills/text2podcast/scripts/synthesize.py.

Invoked as a genuine subprocess throughout, so exit codes are exercised for
real (not just a Python function return value). Google Cloud TTS is mocked
via a `sitecustomize.py` dropped on the subprocess's PYTHONPATH -- this is the
only reliable way to intercept a third-party SDK's client class *before* the
script under test imports it, across a process boundary. ffmpeg is real.
"""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "skills" / "text2podcast" / "scripts" / "synthesize.py"

assert SCRIPT_PATH.is_file(), f"expected to find the skill script at {SCRIPT_PATH}"

_ENV_VARS_TO_STRIP = [
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS", "TTS_MODEL", "LLM_PROVIDER",
]

_SITECUSTOMIZE_TEMPLATE = '''\
import base64
import json
import threading
from unittest.mock import MagicMock

_AUDIO_BYTES = base64.b64decode("__AUDIO_B64__")
_CALLS_LOG = __CALLS_LOG__
_LOCK = threading.Lock()


def _record(entry):
    if _CALLS_LOG is None:
        return
    with _LOCK:
        with open(_CALLS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\\n")


class _FakeTTSClient:
    def synthesize_speech(self, input, voice, audio_config):
        _record({
            "text": input.text,
            "prompt": getattr(input, "prompt", None),
            "voice_name": voice.name,
            "language_code": voice.language_code,
            "model_name": voice.model_name,
        })
        if "FAIL_ME" in input.text:
            raise ValueError("invalid input: simulated synthesis failure")
        resp = MagicMock()
        resp.audio_content = _AUDIO_BYTES
        return resp


import google.cloud.texttospeech as _tts  # noqa: E402
_tts.TextToSpeechClient = lambda *a, **k: _FakeTTSClient()
'''

_BLOCKER_SITECUSTOMIZE = '''\
import sys
import importlib.abc


class _Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "google.cloud.texttospeech":
            raise ImportError("simulated: google-cloud-texttospeech is not installed")
        return None


sys.meta_path.insert(0, _Blocker())
'''


def _write_tts_mock_sitecustomize(dir_path: Path, audio_bytes: bytes, calls_log: Path = None) -> None:
    content = (
        _SITECUSTOMIZE_TEMPLATE
        .replace("__AUDIO_B64__", base64.b64encode(audio_bytes).decode("ascii"))
        .replace("__CALLS_LOG__", repr(str(calls_log)) if calls_log else "None")
    )
    (dir_path / "sitecustomize.py").write_text(content, encoding="utf-8")


def _write_transcript(path: Path, pairs):
    path.write_text(
        json.dumps([{"speaker": s, "text": t} for s, t in pairs]), encoding="utf-8",
    )


def _dummy_credentials_file(tmp_path: Path) -> Path:
    p = tmp_path / "fake-service-account.json"
    p.write_text("{}", encoding="utf-8")
    return p


def _run(args, env_overrides=None, extra_pythonpath=None, script_path=None):
    env = os.environ.copy()
    for var in _ENV_VARS_TO_STRIP:
        env.pop(var, None)
    if extra_pythonpath is not None:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(extra_pythonpath)] + ([existing] if existing else [])
        )
    if env_overrides:
        for key, value in env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value

    return subprocess.run(
        [sys.executable, str(script_path or SCRIPT_PATH), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


# ---------------------------------------------------------------------------
# Bad arguments -> exit 1
# ---------------------------------------------------------------------------

def test_no_arguments_exit_code_1():
    result = _run([])
    assert result.returncode == 1
    assert "error" in result.stderr.lower()


def test_missing_output_argument_exit_code_1(tmp_path):
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])
    result = _run(["--transcript", str(transcript)])
    assert result.returncode == 1


def test_malformed_voice_pair_exit_code_1(tmp_path):
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])
    result = _run([
        "--transcript", str(transcript), "--output", str(tmp_path / "out.mp3"),
        "--voice", "NoEqualsSignHere",
    ])
    assert result.returncode == 1
    assert "Speaker=Voice" in result.stderr or "expected the form" in result.stderr


def test_missing_transcript_file_exit_code_1(tmp_path):
    result = _run([
        "--transcript", str(tmp_path / "does_not_exist.json"),
        "--output", str(tmp_path / "out.mp3"),
    ])
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Preflight checks, each exercised independently
# ---------------------------------------------------------------------------

def test_script_outside_a_checkout_exit_code_1(tmp_path):
    """Copy the script 4 levels deep under an isolated root with no backend/
    sibling, matching its real .claude/skills/text2podcast/scripts/ nesting,
    so parents[4] resolves somewhere that genuinely isn't a Text2Podcast checkout."""
    fake_script_dir = tmp_path / "isolated_root" / "a" / "b" / "scripts"
    fake_script_dir.mkdir(parents=True)
    fake_script = fake_script_dir / "synthesize.py"
    fake_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])

    result = _run(
        ["--transcript", str(transcript), "--output", str(tmp_path / "out.mp3")],
        script_path=fake_script,
    )
    assert result.returncode == 1
    assert "Could not find a Text2Podcast backend" in result.stderr


def test_missing_ffmpeg_exit_code_1(tmp_path):
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])
    empty_bin_dir = tmp_path / "empty_bin"
    empty_bin_dir.mkdir()

    result = _run(
        ["--transcript", str(transcript), "--output", str(tmp_path / "out.mp3")],
        env_overrides={"PATH": str(empty_bin_dir)},
    )
    assert result.returncode == 1
    assert "ffmpeg binary not found" in result.stderr


def test_missing_google_cloud_texttospeech_package_exit_code_1(tmp_path):
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])
    blocker_dir = tmp_path / "blocker"
    blocker_dir.mkdir()
    (blocker_dir / "sitecustomize.py").write_text(_BLOCKER_SITECUSTOMIZE, encoding="utf-8")

    result = _run(
        ["--transcript", str(transcript), "--output", str(tmp_path / "out.mp3")],
        extra_pythonpath=blocker_dir,
    )
    assert result.returncode == 1
    assert "google-cloud-texttospeech" in result.stderr


def test_credentials_file_that_does_not_exist_exit_code_1(tmp_path):
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])
    missing_cred = tmp_path / "nonexistent-creds.json"

    result = _run(
        ["--transcript", str(transcript), "--output", str(tmp_path / "out.mp3")],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(missing_cred)},
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_absent_credentials_exit_code_1(tmp_path):
    # Guard: this assertion is only meaningful if this sandbox genuinely has no
    # ambient Application Default Credentials.
    import google.auth
    try:
        google.auth.default()
    except Exception:
        pass
    else:
        pytest.skip("ambient Application Default Credentials are present in this environment")

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hi")])

    result = _run(
        ["--transcript", str(transcript), "--output", str(tmp_path / "out.mp3")],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": None},
    )
    assert result.returncode == 1
    assert "No Google Cloud credentials found" in result.stderr


# ---------------------------------------------------------------------------
# Success / partial / all-fail exit codes, with TTS mocked via sitecustomize
# ---------------------------------------------------------------------------

def test_success_exit_code_0(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hello"), ("Speaker 2", "hi back")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out)],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path))},
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "Output:" in result.stdout
    assert "2 succeeded, 0 failed, 2 total" in result.stdout


def test_partial_failure_exit_code_2_names_failed_segments(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hello"), ("Speaker 2", "FAIL_ME oops")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out)],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path))},
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 2, result.stderr
    assert out.exists()  # partial success still produces output
    assert "1 of 2 segment(s) failed" in result.stderr
    assert "segment 2" in result.stderr


def test_all_fail_exit_code_1(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "FAIL_ME a"), ("Speaker 2", "FAIL_ME b")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out)],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path))},
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 1, result.stderr
    assert not out.exists()
    assert "failed to synthesize" in result.stderr.lower()


# ---------------------------------------------------------------------------
# --voice / --style / --model / --language reach the synthesis call
# ---------------------------------------------------------------------------

def test_voice_style_model_language_reach_synthesis_call(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    calls_log = tmp_path / "calls.jsonl"
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes, calls_log=calls_log)

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hello")])
    out = tmp_path / "out.mp3"

    result = _run(
        [
            "--transcript", str(transcript), "--output", str(out),
            "--voice", "Speaker 1=Puck",
            "--style", "Speaker 1=Speak like a pirate",
            "--model", "custom-model-x",
            "--language", "en-GB",
        ],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path))},
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in calls_log.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 1
    call = calls[0]
    assert call["voice_name"] == "Puck"
    assert call["prompt"] == "Speak like a pirate"
    assert call["model_name"] == "custom-model-x"
    assert call["language_code"] == "en-GB"


def test_unspecified_speaker_falls_back_to_module_defaults(tmp_path, real_short_mp3_bytes):
    """--voice "Speaker 1=Puck" alone must not blow away Speaker 2's default
    voice -- covers the module docstring's explicit reasoning for seeding
    voice_settings with DEFAULT_SPEAKER_VOICES before layering overrides."""
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    calls_log = tmp_path / "calls.jsonl"
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes, calls_log=calls_log)

    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "a"), ("Speaker 2", "b")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out), "--voice", "Speaker 1=Puck"],
        env_overrides={"GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path))},
        extra_pythonpath=mock_dir,
    )
    assert result.returncode == 0, result.stderr

    calls = {json.loads(line)["text"]: json.loads(line) for line in calls_log.read_text(encoding="utf-8").splitlines()}
    assert calls["a"]["voice_name"] == "Puck"
    assert calls["b"]["voice_name"] == "Charon"  # DEFAULT_SPEAKER_VOICES["Speaker 2"], untouched


# ---------------------------------------------------------------------------
# Segment cleanup vs. --keep-segments
# ---------------------------------------------------------------------------

def test_segments_cleaned_up_by_default(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

    isolated_tmp = tmp_path / "isolated_tmp"
    isolated_tmp.mkdir()
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hello")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out)],
        env_overrides={
            "GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path)),
            "TMPDIR": str(isolated_tmp),
        },
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 0, result.stderr
    assert "Segment files kept at" not in result.stdout
    assert list(isolated_tmp.glob("text2podcast-segments-*")) == []


def test_keep_segments_flag_preserves_working_directory(tmp_path, real_short_mp3_bytes):
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    _write_tts_mock_sitecustomize(mock_dir, real_short_mp3_bytes)

    isolated_tmp = tmp_path / "isolated_tmp"
    isolated_tmp.mkdir()
    transcript = tmp_path / "t.json"
    _write_transcript(transcript, [("Speaker 1", "hello")])
    out = tmp_path / "out.mp3"

    result = _run(
        ["--transcript", str(transcript), "--output", str(out), "--keep-segments"],
        env_overrides={
            "GOOGLE_APPLICATION_CREDENTIALS": str(_dummy_credentials_file(tmp_path)),
            "TMPDIR": str(isolated_tmp),
        },
        extra_pythonpath=mock_dir,
    )

    assert result.returncode == 0, result.stderr
    assert "Segment files kept at" in result.stdout
    leftover = list(isolated_tmp.glob("text2podcast-segments-*"))
    assert len(leftover) == 1
    assert (leftover[0] / "metadata.json").exists()
