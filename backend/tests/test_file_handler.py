"""
Tests for app.utils.file_handler: JSON transcript round-trip, the legacy
ast.literal_eval fallback, malformed-input rejection, and -- specifically --
that eval() is never reachable even for a file crafted to look like a Python
literal containing a call expression (ast.literal_eval rejects those).
"""
import json

import pytest

from app.utils.file_handler import (
    load_metadata, load_transcript, save_metadata, save_transcript,
)


def test_save_and_load_transcript_round_trip_preserves_cjk(tmp_path):
    transcript = [
        ("Speaker 1", "歡迎收聽今天的節目，我們來聊聊人工智慧。"),
        ("Speaker 2", "沒錯，這是一個很有趣的話題！"),
    ]
    path = tmp_path / "transcript.json"

    saved_path = save_transcript(transcript, path)
    assert saved_path == path

    # ensure_ascii=False -- the file on disk should contain real CJK
    # characters, not \uXXXX escapes.
    raw = path.read_text(encoding="utf-8")
    assert "歡迎收聽" in raw
    assert "\\u" not in raw

    loaded = load_transcript(path)
    assert loaded == transcript


def test_save_transcript_writes_speaker_text_json_objects(tmp_path):
    path = tmp_path / "t.json"
    save_transcript([("Speaker 1", "hi")], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == [{"speaker": "Speaker 1", "text": "hi"}]


def test_load_transcript_legacy_python_repr_format(tmp_path):
    """
    Older files stored str(list_of_tuples) -- a Python repr -- instead of
    JSON. load_transcript must still read these back via ast.literal_eval.
    """
    path = tmp_path / "legacy.txt"
    legacy_content = repr([("Speaker 1", "hello there"), ("Speaker 2", "hi!")])
    path.write_text(legacy_content, encoding="utf-8")

    loaded = load_transcript(path)
    assert loaded == [("Speaker 1", "hello there"), ("Speaker 2", "hi!")]


def test_load_transcript_legacy_repr_preserves_cjk(tmp_path):
    path = tmp_path / "legacy_cjk.txt"
    legacy = [("講者1", "你好，歡迎收聽")]
    path.write_text(repr(legacy), encoding="utf-8")

    assert load_transcript(path) == legacy


@pytest.mark.parametrize("bad_payload", [
    '{"not": "a list"}',
    '"just a string"',
    "42",
])
def test_load_transcript_rejects_non_list(tmp_path, bad_payload):
    path = tmp_path / "bad.json"
    path.write_text(bad_payload, encoding="utf-8")
    with pytest.raises(ValueError, match="must be a list"):
        load_transcript(path)


def test_load_transcript_rejects_wrong_tuple_arity(tmp_path):
    path = tmp_path / "bad_arity.txt"
    # A 3-tuple, not the required 2-element (speaker, text) pair.
    path.write_text(repr([("Speaker 1", "text", "extra")]), encoding="utf-8")
    with pytest.raises(ValueError, match="2-element"):
        load_transcript(path)


def test_load_transcript_rejects_1_tuple(tmp_path):
    path = tmp_path / "bad_arity2.txt"
    path.write_text(repr([("Speaker 1",)]), encoding="utf-8")
    with pytest.raises(ValueError, match="2-element"):
        load_transcript(path)


def test_load_transcript_rejects_non_string_members(tmp_path):
    path = tmp_path / "bad_members.txt"
    path.write_text(repr([("Speaker 1", 12345)]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"\(str, str\)"):
        load_transcript(path)


def test_load_transcript_rejects_non_string_speaker(tmp_path):
    path = tmp_path / "bad_speaker.txt"
    path.write_text(repr([(1, "text")]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"\(str, str\)"):
        load_transcript(path)


def test_load_transcript_json_dict_items_missing_keys_raise(tmp_path):
    """A JSON list of dicts missing "speaker"/"text" should fail validation
    (get() returns None, which is not a str), not silently produce garbage."""
    path = tmp_path / "bad_dicts.json"
    path.write_text(json.dumps([{"speaker": "Speaker 1"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_transcript(path)


def test_load_transcript_unparsable_content_raises_value_error(tmp_path):
    path = tmp_path / "garbage.txt"
    path.write_text("this is neither JSON nor a Python literal {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to parse transcript file"):
        load_transcript(path)


def test_load_transcript_never_reaches_eval_for_call_expression(tmp_path):
    """
    A transcript file containing something that looks like an RCE payload
    must raise, not execute. ast.literal_eval (used internally, never eval())
    rejects any node that isn't a literal -- including call expressions --
    with a ValueError, so this must never actually invoke os.system.
    """
    path = tmp_path / "malicious.txt"
    path.write_text('__import__("os").system("touch /tmp/pwned_by_test")', encoding="utf-8")

    with pytest.raises(ValueError):
        load_transcript(path)

    # Belt-and-suspenders: prove the payload really did not run.
    from pathlib import Path
    assert not Path("/tmp/pwned_by_test").exists()


def test_load_transcript_never_reaches_eval_list_of_call_expressions(tmp_path):
    """Same RCE guard, but shaped like a plausible (still malicious) transcript:
    a list whose second element is a call expression instead of a string."""
    path = tmp_path / "malicious_list.txt"
    path.write_text(
        '[("Speaker 1", __import__("os").system("touch /tmp/pwned_by_test_2"))]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_transcript(path)

    from pathlib import Path
    assert not Path("/tmp/pwned_by_test_2").exists()


def test_save_and_load_metadata_round_trip(tmp_path):
    path = tmp_path / "metadata.json"
    metadata = {"total_segments": 2, "success": 2, "failed": 0, "audio_files": []}
    save_metadata(metadata, path)
    assert load_metadata(path) == metadata
