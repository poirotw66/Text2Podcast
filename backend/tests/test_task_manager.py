"""
Tests for app.services.task_manager: TTL expiry, max-count eviction
(oldest-first), output-directory cleanup on eviction, and -- the two real bugs
this suite is specifically written to catch -- a direct regression test for
_signal_update surviving a closed event loop, exercised both directly and via
set_task_error (where the original bug masked the real error being recorded).
"""
import asyncio
from datetime import datetime, timedelta

from app.models.schemas import TaskStatus
from app.services.task_manager import TaskManager


def _age(task_manager: TaskManager, task_id: str, seconds_ago: float) -> None:
    """Back-date a task's updated_at without needing to actually sleep."""
    task_manager.tasks[task_id].updated_at = datetime.now() - timedelta(seconds=seconds_ago)


def test_create_and_get_task_round_trip():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hello world")
    task = tm.get_task(task_id)
    assert task is not None
    assert task.task_id == task_id
    assert task.text_content == "hello world"
    assert task.status == TaskStatus.PENDING


def test_get_unknown_task_returns_none():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    assert tm.get_task("does-not-exist") is None


def test_ttl_expiry_evicts_task_on_next_access(isolated_outputs_dir):
    tm = TaskManager(ttl_seconds=1, max_tasks=100)
    task_id = tm.create_task("hi")
    _age(tm, task_id, seconds_ago=5)  # older than the 1s TTL

    assert tm.get_task(task_id) is None
    assert task_id not in tm.tasks


def test_task_within_ttl_is_not_evicted(isolated_outputs_dir):
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    _age(tm, task_id, seconds_ago=5)  # well within a 1h TTL

    assert tm.get_task(task_id) is not None


def test_max_count_eviction_is_oldest_first(isolated_outputs_dir):
    tm = TaskManager(ttl_seconds=3600, max_tasks=3)
    ids = [tm.create_task(f"task-{i}") for i in range(3)]
    # Spread updated_at out so ordering is unambiguous regardless of clock
    # resolution: ids[0] is oldest, ids[2] is newest.
    for rank, tid in enumerate(ids):
        _age(tm, tid, seconds_ago=(len(ids) - rank) * 100)

    new_id = tm.create_task("task-new")  # pushes the store to 4, over the cap of 3

    assert tm.get_task(ids[0]) is None       # oldest evicted
    assert tm.get_task(ids[1]) is not None
    assert tm.get_task(ids[2]) is not None
    assert tm.get_task(new_id) is not None
    assert len(tm.tasks) == 3


def test_eviction_cleans_up_output_directory(isolated_outputs_dir):
    tm = TaskManager(ttl_seconds=1, max_tasks=100)
    task_id = tm.create_task("hi")

    task_dir = isolated_outputs_dir / task_id
    task_dir.mkdir()
    (task_dir / "merged_audio.mp3").write_bytes(b"fake-audio")
    assert task_dir.exists()

    _age(tm, task_id, seconds_ago=10)
    assert tm.get_task(task_id) is None
    assert not task_dir.exists()


def test_non_evicted_tasks_output_directory_is_left_alone(isolated_outputs_dir):
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    task_dir = isolated_outputs_dir / task_id
    task_dir.mkdir()
    (task_dir / "merged_audio.mp3").write_bytes(b"fake-audio")

    assert tm.get_task(task_id) is not None
    assert task_dir.exists()


def test_update_task_status_updates_fields_and_timestamp():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    before = tm.get_task(task_id).updated_at

    ok = tm.update_task_status(
        task_id, TaskStatus.COMPLETED, progress=100, message="done",
        total_segments=5, failed_segments=1,
    )
    assert ok is True

    task = tm.get_task(task_id)
    assert task.status == TaskStatus.COMPLETED
    assert task.progress == 100
    assert task.message == "done"
    assert task.total_segments == 5
    assert task.failed_segments == 1
    assert task.partial is True
    assert task.updated_at >= before


def test_update_task_status_unknown_task_returns_false():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    assert tm.update_task_status("nope", TaskStatus.COMPLETED) is False


def test_set_task_error_sets_failed_status():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    assert tm.set_task_error(task_id, "boom") is True

    task = tm.get_task(task_id)
    assert task.status == TaskStatus.FAILED
    assert task.error == "boom"


def test_set_task_files():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    assert tm.set_task_files(task_id, audio_file="a.mp3", transcript_file="t.txt") is True

    task = tm.get_task(task_id)
    assert task.audio_file == "a.mp3"
    assert task.transcript_file == "t.txt"


# ---------------------------------------------------------------------------
# The bug this brief calls out explicitly: _signal_update used to call
# call_soon_threadsafe on a captured event loop that had since closed, raising
# inside set_task_error and masking the *original* error being recorded.
# Testing TaskManager in isolation (as below) is exactly the level at which
# the real bug was previously missed -- it only showed up under a real async
# client where the loop genuinely closes mid-generation. These tests simulate
# that same "loop captured, then closed" condition directly.
# ---------------------------------------------------------------------------

def test_signal_update_does_not_raise_with_closed_loop():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    task = tm.get_task(task_id)

    loop = asyncio.new_event_loop()
    loop.close()
    tm._loop = loop  # simulate a loop captured earlier that has since closed

    # Must not raise.
    tm._signal_update(task)
    assert task.update_event.is_set()


def test_set_task_error_survives_closed_loop_and_still_records_the_error():
    """
    The regression this bug caused: set_task_error() -> _signal_update() ->
    call_soon_threadsafe() on a closed loop raised RuntimeError, which
    propagated out of set_task_error() and masked the original error the
    caller was trying to record. This must no longer happen.
    """
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    task = tm.get_task(task_id)

    loop = asyncio.new_event_loop()
    loop.close()
    tm._loop = loop

    # This call must not raise -- if it did, the caller's real error (whatever
    # it was trying to report via set_task_error) would be masked.
    ok = tm.set_task_error(task_id, "the real underlying error")

    assert ok is True
    assert task.status == TaskStatus.FAILED
    assert task.error == "the real underlying error"
    assert task.update_event.is_set()


def test_update_task_status_also_survives_closed_loop():
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    task = tm.get_task(task_id)

    loop = asyncio.new_event_loop()
    loop.close()
    tm._loop = loop

    ok = tm.update_task_status(task_id, TaskStatus.PROCESSING, progress=10)
    assert ok is True
    assert task.status == TaskStatus.PROCESSING
    assert task.update_event.is_set()


def test_signal_update_uses_live_loop_when_available():
    """Sanity check for the non-broken path: with a real, running loop, the
    update_event is scheduled via call_soon_threadsafe and gets set once the
    loop runs -- not merely set synchronously (that fallback is closed-loop-only)."""
    tm = TaskManager(ttl_seconds=3600, max_tasks=100)
    task_id = tm.create_task("hi")
    task = tm.get_task(task_id)

    async def _run():
        tm._capture_loop()
        tm._signal_update(task)
        # Let the scheduled call_soon_threadsafe callback actually run.
        await asyncio.sleep(0)

    asyncio.run(_run())
    assert task.update_event.is_set()
