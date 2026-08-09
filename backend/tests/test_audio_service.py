"""
Tests for app.services.audio_service.

The TTS client is always mocked (via the `mock_tts` fixture in conftest.py --
no Google Cloud credentials exist in this environment) but ffmpeg is real:
merges run against real short mp3s and are checked with real ffprobe duration
measurements.
"""
import json
import shutil
from pathlib import Path

import pytest

from app.services.audio_service import AudioService, _require_ffmpeg
from tests.conftest import ffprobe_duration_seconds

# Tolerance for real ffmpeg/lame encoding overhead (frame padding etc.) on top
# of the nominal durations we ask for.
DURATION_TOLERANCE_SECONDS = 0.4


def _write_metadata(path, audio_files, total_segments=None):
    metadata = {
        "total_segments": total_segments if total_segments is not None else len(audio_files),
        "success": sum(1 for a in audio_files if a.get("success", True)),
        "failed": sum(1 for a in audio_files if not a.get("success", True)),
        "model_used": "test-model",
        "language_code": "cmn-tw",
        "audio_files": audio_files,
    }
    path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


# ---------------------------------------------------------------------------
# generate_audio_from_transcript
# ---------------------------------------------------------------------------

def test_generate_audio_from_transcript_all_success(tmp_path, mock_tts):
    service = AudioService()
    transcript = [("Speaker 1", "hello there"), ("Speaker 2", "hi back")]

    result = service.generate_audio_from_transcript(transcript, tmp_path, max_workers=2)

    assert result["success"] == 2
    assert result["failed"] == 0
    assert len(result["audio_files"]) == 2
    for entry in result["audio_files"]:
        assert entry["success"] is True
        assert entry["error"] is None
        assert Path(entry["file"]).exists()

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["total_segments"] == 2
    assert metadata["success"] == 2
    assert metadata["failed"] == 0


def test_metadata_records_every_segment_including_failures(tmp_path, mock_tts):
    service = AudioService()
    transcript = [
        ("Speaker 1", "this one is fine"),
        ("Speaker 2", "FAIL_ME this one blows up"),
        ("Speaker 1", "this one is fine too"),
    ]

    result = service.generate_audio_from_transcript(transcript, tmp_path, max_workers=1)

    assert result["success"] == 2
    assert result["failed"] == 1
    assert len(result["audio_files"]) == 3  # every segment recorded, success and failure alike

    by_index = {e["index"]: e for e in result["audio_files"]}
    assert by_index[1]["success"] is True and by_index[1]["error"] is None
    assert by_index[2]["success"] is False
    assert "invalid" in by_index[2]["error"].lower()
    assert by_index[3]["success"] is True and by_index[3]["error"] is None

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["total_segments"] == 3
    assert metadata["success"] == 2
    assert metadata["failed"] == 1
    assert len(metadata["audio_files"]) == 3


def test_voice_routing_exact_match(tmp_path, mock_tts):
    service = AudioService()
    transcript = [("Speaker 1", "a"), ("Speaker 2", "b")]
    voice_settings = {"Speaker 1": "Kore", "Speaker 2": "Charon"}

    service.generate_audio_from_transcript(
        transcript, tmp_path, max_workers=1, voice_settings=voice_settings,
    )

    used = {c["text"]: c["voice_name"] for c in mock_tts}
    assert used["a"] == "Kore"
    assert used["b"] == "Charon"


def test_voice_routing_falls_back_via_digit_match(tmp_path, mock_tts):
    """A speaker name that isn't an exact key (e.g. '講者2') should still map
    to the "Speaker 2" voice via the digit-extraction fallback."""
    service = AudioService()
    transcript = [("講者2", "chinese speaker two")]
    voice_settings = {"Speaker 1": "Kore", "Speaker 2": "Charon"}

    service.generate_audio_from_transcript(
        transcript, tmp_path, max_workers=1, voice_settings=voice_settings,
    )

    assert mock_tts[0]["voice_name"] == "Charon"


def test_voice_routing_unmapped_speaker_falls_back_to_hardcoded_default(tmp_path, mock_tts):
    """A speaker with no digit at all in its name (no exact match, no regex
    match) falls back to the hardcoded "Kore" default -- not DEFAULT_SPEAKER_VOICES."""
    service = AudioService()
    transcript = [("Narrator", "no digits here")]
    voice_settings = {"Speaker 1": "Kore", "Speaker 2": "Charon"}

    service.generate_audio_from_transcript(
        transcript, tmp_path, max_workers=1, voice_settings=voice_settings,
    )

    assert mock_tts[0]["voice_name"] == "Kore"


def test_style_routing_exact_and_fallback(tmp_path, mock_tts):
    service = AudioService()
    transcript = [
        ("Speaker 1", "styled"),
        ("Speaker 2", "unstyled but numbered"),
        ("Narrator", "no style at all"),
    ]
    style_settings = {"Speaker 1": "Speak warmly and conversationally"}

    service.generate_audio_from_transcript(
        transcript, tmp_path, max_workers=1, style_settings=style_settings,
    )

    prompts = {c["text"]: c["prompt"] for c in mock_tts}
    assert prompts["styled"] == "Speak warmly and conversationally"
    # "Speaker 2" has no entry in style_settings -> module default prompt.
    from app.services.audio_service import DEFAULT_TTS_PROMPT
    assert prompts["unstyled but numbered"] == DEFAULT_TTS_PROMPT
    assert prompts["no style at all"] == DEFAULT_TTS_PROMPT


def test_model_and_language_reach_synthesis_call_and_metadata(tmp_path, mock_tts):
    """
    Regression coverage for the documented bug: model/language_code must be
    reachable as explicit per-call arguments (not only via mutating module
    globals). Assert both the synthesize_speech call and metadata.json reflect
    the caller-supplied values.
    """
    service = AudioService()
    transcript = [("Speaker 1", "hello")]

    result = service.generate_audio_from_transcript(
        transcript, tmp_path, max_workers=1,
        model="custom-tts-model", language_code="en-US",
    )

    assert mock_tts[0]["model_name"] == "custom-tts-model"
    assert mock_tts[0]["language_code"] == "en-US"

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["model_used"] == "custom-tts-model"
    assert metadata["language_code"] == "en-US"
    assert result["metadata_file"] == str(tmp_path / "metadata.json")


def test_model_and_language_default_to_current_module_globals(tmp_path, mock_tts, monkeypatch):
    """
    When model/language_code aren't passed explicitly, generate_audio_from_transcript
    re-reads the *current* module-level TTS_MODEL/LANGUAGE_CODE globals at call
    time (not a value bound once at import time) -- so mutating the module
    globals after import still reaches the synthesis call.
    """
    import app.services.audio_service as audio_service_module
    monkeypatch.setattr(audio_service_module, "TTS_MODEL", "globally-configured-model")
    monkeypatch.setattr(audio_service_module, "LANGUAGE_CODE", "ja-JP")

    service = AudioService()
    service.generate_audio_from_transcript([("Speaker 1", "hi")], tmp_path, max_workers=1)

    assert mock_tts[0]["model_name"] == "globally-configured-model"
    assert mock_tts[0]["language_code"] == "ja-JP"


# ---------------------------------------------------------------------------
# merge_audio_files -- real ffmpeg
# ---------------------------------------------------------------------------

def test_merge_audio_files_real_ffmpeg_produces_expected_duration(tmp_path, real_short_mp3_bytes):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()

    files = []
    for i in (1, 2):
        f = seg_dir / f"seg_{i}.mp3"
        f.write_bytes(real_short_mp3_bytes)
        files.append(f)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(files[0]), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "b", "voice": "Charon",
         "file": str(files[1]), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files)

    out_file = tmp_path / "merged.mp3"
    result = service.merge_audio_files(metadata_file, out_file, silence_duration_ms=500)

    assert result == out_file
    assert out_file.exists()

    # 2 x 1.0s segments + 1 x 0.5s inter-segment silence = 2.5s
    duration = ffprobe_duration_seconds(out_file)
    assert abs(duration - 2.5) < DURATION_TOLERANCE_SECONDS, duration


def test_merge_audio_files_no_silence_when_requested(tmp_path, real_short_mp3_bytes):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    files = []
    for i in (1, 2):
        f = seg_dir / f"seg_{i}.mp3"
        f.write_bytes(real_short_mp3_bytes)
        files.append(f)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(files[0]), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "b", "voice": "Charon",
         "file": str(files[1]), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files)

    out_file = tmp_path / "merged.mp3"
    service.merge_audio_files(metadata_file, out_file, silence_duration_ms=0)

    duration = ffprobe_duration_seconds(out_file)
    assert abs(duration - 2.0) < DURATION_TOLERANCE_SECONDS, duration


def test_merge_audio_files_missing_middle_segment_silence_position_is_by_full_list_index(
    tmp_path, real_short_mp3_bytes
):
    """
    Deliberate, documented behaviour (see merge_audio_files' docstring/comment):
    silence placement is keyed to an entry's position in the *full* audio_files
    list, not to its position among the segments that actually survive onto
    disk. This test asserts that behaviour rather than "fixing" it.

    With 3 segments where the middle one failed: only segment 1 and segment 3
    are written to the concat list. Silence is written after segment 1 (index
    1 < total 3) but NOT after segment 3 (index 3 is not < total 3), giving
    exactly one gap -- the same shape you'd get from a naive "gap between
    survivors" implementation, so this case alone doesn't distinguish the two.
    See the sibling test below (missing *last* segment) for the case that does.
    """
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "seg_1.mp3"
    f1.write_bytes(real_short_mp3_bytes)
    f3 = seg_dir / "seg_3.mp3"
    f3.write_bytes(real_short_mp3_bytes)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "b", "voice": "Charon",
         "file": str(seg_dir / "seg_2.mp3"), "success": False, "error": "simulated failure"},
        {"index": 3, "speaker": "Speaker 1", "text": "c", "voice": "Kore",
         "file": str(f3), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files, total_segments=3)

    out_file = tmp_path / "merged.mp3"
    service.merge_audio_files(metadata_file, out_file, silence_duration_ms=500)

    # 2 surviving segments (1.0s each) + 1 gap (0.5s) = 2.5s
    duration = ffprobe_duration_seconds(out_file)
    assert abs(duration - 2.5) < DURATION_TOLERANCE_SECONDS, duration


def test_merge_audio_files_missing_last_segment_still_gets_trailing_silence(
    tmp_path, real_short_mp3_bytes
):
    """
    This is the case that actually distinguishes "keyed to full-list position"
    from "keyed to survivor position": when the LAST segment of 3 fails, a
    naive "insert a gap between each pair of survivors" implementation would
    produce exactly one gap (after segment 1, between the two survivors) and
    no trailing silence. The real implementation instead checks `i <
    total_segments` using each entry's original index, so segment 2 (index 2,
    2 < 3) still gets a trailing silence written after it even though it's now
    the last thing in the output. Assert that extra trailing gap exists,
    exactly as documented -- this is intentional, not a bug to fix.
    """
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "seg_1.mp3"
    f1.write_bytes(real_short_mp3_bytes)
    f2 = seg_dir / "seg_2.mp3"
    f2.write_bytes(real_short_mp3_bytes)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "b", "voice": "Charon",
         "file": str(f2), "success": True, "error": None},
        {"index": 3, "speaker": "Speaker 1", "text": "c", "voice": "Kore",
         "file": str(seg_dir / "seg_3.mp3"), "success": False, "error": "simulated failure"},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files, total_segments=3)

    out_file = tmp_path / "merged.mp3"
    service.merge_audio_files(metadata_file, out_file, silence_duration_ms=500)

    duration = ffprobe_duration_seconds(out_file)
    # "Fixed" (survivor-position) behaviour would give 2 x 1.0s + 1 x 0.5s = 2.5s.
    # Actual (full-list-position) behaviour gives 2 x 1.0s + 2 x 0.5s = 3.0s,
    # because segment 2 (index 2 < total 3) still gets a trailing gap.
    assert abs(duration - 3.0) < DURATION_TOLERANCE_SECONDS, duration
    assert duration > 2.5 + DURATION_TOLERANCE_SECONDS  # clearly distinguishable from the "fixed" shape


def test_merge_audio_files_skips_missing_files_on_disk(tmp_path, real_short_mp3_bytes):
    """A metadata entry marked success=True but whose file doesn't actually
    exist on disk is skipped with a warning, not a crash."""
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "seg_1.mp3"
    f1.write_bytes(real_short_mp3_bytes)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "b", "voice": "Charon",
         "file": str(seg_dir / "does_not_exist.mp3"), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files)

    out_file = tmp_path / "merged.mp3"
    result = service.merge_audio_files(metadata_file, out_file, silence_duration_ms=500)
    assert result == out_file

    # Only segment 1 (1.0s) survives onto disk, but the full-list-position
    # silence rule (see the dedicated tests below) still writes a trailing
    # gap after it, since its index (1) is < total_segments (2).
    duration = ffprobe_duration_seconds(out_file)
    assert abs(duration - 1.5) < DURATION_TOLERANCE_SECONDS, duration


def test_merge_audio_files_returns_none_when_no_segments_exist_on_disk(tmp_path):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(seg_dir / "missing.mp3"), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files)

    out_file = tmp_path / "merged.mp3"
    result = service.merge_audio_files(metadata_file, out_file)
    assert result is None
    assert not out_file.exists()


def test_merge_audio_files_returns_none_for_empty_audio_files_list(tmp_path):
    service = AudioService()
    metadata_file = tmp_path / "metadata.json"
    _write_metadata(metadata_file, [])
    out_file = tmp_path / "merged.mp3"
    assert service.merge_audio_files(metadata_file, out_file) is None


# ---------------------------------------------------------------------------
# regenerate_segment
# ---------------------------------------------------------------------------

def test_regenerate_segment_replaces_entry_and_recomputes_counts(tmp_path, real_short_mp3_bytes, mock_tts):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "Speaker_1_001.mp3"
    f1.write_bytes(real_short_mp3_bytes)
    f2 = seg_dir / "Speaker_2_002.mp3"
    # segment 2 previously failed -- no file on disk for it

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "original good text", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
        {"index": 2, "speaker": "Speaker 2", "text": "FAIL_ME original bad text", "voice": "Charon",
         "file": str(f2), "success": False, "error": "invalid: simulated synthesis failure"},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files, total_segments=2)

    result = service.regenerate_segment(
        metadata_file, segment_index=2, text="a fixed segment", voice="Puck",
    )

    assert result["regenerated_success"] is True
    assert result["regenerated_error"] is None
    assert result["total_segments"] == 2
    assert result["success"] == 2
    assert result["failed"] == 0

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    entry2 = next(e for e in metadata["audio_files"] if e["index"] == 2)
    assert entry2["text"] == "a fixed segment"
    assert entry2["voice"] == "Puck"
    assert entry2["success"] is True
    assert entry2["error"] is None
    assert f2.exists()
    assert f2.read_bytes() == real_short_mp3_bytes

    # Segment 1 untouched.
    entry1 = next(e for e in metadata["audio_files"] if e["index"] == 1)
    assert entry1["text"] == "original good text"

    # And the mock TTS was actually called for the regenerated text/voice.
    assert any(c["text"] == "a fixed segment" and c["voice_name"] == "Puck" for c in mock_tts)


def test_regenerate_segment_reuses_existing_text_and_voice_when_omitted(tmp_path, real_short_mp3_bytes, mock_tts):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "Speaker_1_001.mp3"
    f1.write_bytes(real_short_mp3_bytes)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "keep this text", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files, total_segments=1)

    service.regenerate_segment(metadata_file, segment_index=1)

    assert mock_tts[-1]["text"] == "keep this text"
    assert mock_tts[-1]["voice_name"] == "Kore"


def test_regenerate_segment_unknown_index_raises_value_error(tmp_path):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(seg_dir / "x.mp3"), "success": True, "error": None},
    ])

    with pytest.raises(ValueError, match="Segment index 99"):
        service.regenerate_segment(metadata_file, segment_index=99)


def test_regenerate_segment_can_turn_a_success_into_a_failure(tmp_path, real_short_mp3_bytes, mock_tts):
    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "Speaker_1_001.mp3"
    f1.write_bytes(real_short_mp3_bytes)

    audio_files = [
        {"index": 1, "speaker": "Speaker 1", "text": "was fine", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
    ]
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, audio_files, total_segments=1)

    result = service.regenerate_segment(metadata_file, segment_index=1, text="FAIL_ME now broken")

    assert result["regenerated_success"] is False
    assert result["failed"] == 1
    assert result["success"] == 0
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["audio_files"][0]["success"] is False


# ---------------------------------------------------------------------------
# ffmpeg absence
# ---------------------------------------------------------------------------

def test_require_ffmpeg_raises_clearly_when_absent(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="ffmpeg binary not found"):
        _require_ffmpeg()


def test_merge_audio_files_raises_when_ffmpeg_absent(tmp_path, monkeypatch, real_short_mp3_bytes):
    import app.services.audio_service as audio_service_module
    monkeypatch.setattr(audio_service_module.shutil, "which", lambda name: None)

    service = AudioService()
    seg_dir = tmp_path / "segs"
    seg_dir.mkdir()
    f1 = seg_dir / "seg_1.mp3"
    f1.write_bytes(real_short_mp3_bytes)
    metadata_file = seg_dir / "metadata.json"
    _write_metadata(metadata_file, [
        {"index": 1, "speaker": "Speaker 1", "text": "a", "voice": "Kore",
         "file": str(f1), "success": True, "error": None},
    ])

    with pytest.raises(RuntimeError, match="ffmpeg binary not found"):
        service.merge_audio_files(metadata_file, tmp_path / "out.mp3")
