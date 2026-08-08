"""
Task manager for tracking job status and progress

IMPORTANT — single-process constraint: this store keeps all task state in an
in-memory dict inside one Python process. It is NOT shared across processes, so
running the API with `uvicorn --workers >1` (or any multi-process deployment)
silently breaks it: a request can land on a worker process that never created
(or never updated) the task it's asking about. Run this API with a single worker
until TaskManager is backed by something shared (Redis, SQLite, etc.).

To make that swap possible without touching call sites, TaskManager implements
TaskStore below — a small abstract interface capturing every operation the rest
of the app needs. A future RedisTaskStore/SQLiteTaskStore can simply implement
the same interface and be handed to get_task_manager() as a drop-in replacement.
This module does not implement such a backend; only the in-memory one.
"""
import asyncio
import logging
import os
import shutil
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from app.models.schemas import TaskStatus

logger = logging.getLogger(__name__)

# backend/outputs/<task_id>/ — cleaned up whenever a task is evicted.
OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"

# How long a task is kept after its last update before it's eligible for eviction.
DEFAULT_TASK_TTL_SECONDS = 24 * 60 * 60  # 24h
# Hard cap on the number of tasks kept in memory; oldest-updated tasks are evicted first.
DEFAULT_MAX_TASKS = 1000


class Task:
    """Task model"""

    def __init__(self, task_id: str, text_content: str):
        self.task_id = task_id
        self.text_content = text_content
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.message: Optional[str] = None
        self.error: Optional[str] = None
        self.audio_file: Optional[str] = None
        self.transcript_file: Optional[str] = None
        # Populated once audio generation has run at least once for this task (initial
        # Step 3 or a later regeneration). None beforehand.
        self.total_segments: Optional[int] = None
        self.failed_segments: Optional[int] = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        # Set (via TaskManager) whenever this task's status/progress/files change, so
        # the SSE stream can await it instead of polling the task dict every second.
        self.update_event = asyncio.Event()

    @property
    def partial(self) -> bool:
        """True iff the most recent audio generation had at least one failed segment."""
        return bool(self.failed_segments)

    def update_status(
        self,
        status: TaskStatus,
        progress: int = None,
        message: str = None,
        total_segments: int = None,
        failed_segments: int = None
    ):
        """Update task status"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if message:
            self.message = message
        if total_segments is not None:
            self.total_segments = total_segments
        if failed_segments is not None:
            self.failed_segments = failed_segments
        self.updated_at = datetime.now()

    def set_error(self, error: str):
        """Set error message"""
        self.error = error
        self.status = TaskStatus.FAILED
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "audio_file": self.audio_file,
            "transcript_file": self.transcript_file,
            "total_segments": self.total_segments,
            "failed_segments": self.failed_segments,
            "partial": self.partial,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class TaskStore(ABC):
    """
    Minimal interface the rest of the app depends on. Implement this to swap the
    in-memory TaskManager for a shared backend (Redis, SQLite, ...) without changing
    any call site.
    """

    @abstractmethod
    def create_task(self, text_content: str) -> str: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]: ...

    @abstractmethod
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int = None,
        message: str = None,
        total_segments: int = None,
        failed_segments: int = None
    ) -> bool: ...

    @abstractmethod
    def set_task_error(self, task_id: str, error: str) -> bool: ...

    @abstractmethod
    def set_task_files(
        self, task_id: str, audio_file: str = None, transcript_file: str = None
    ) -> bool: ...


class TaskManager(TaskStore):
    """
    In-memory task manager.

    Thread-safe: every mutation (and the eviction sweep) is guarded by a
    threading.Lock, since task state can be updated both from the asyncio event
    loop thread and from worker threads in the audio-generation pipeline.
    """

    def __init__(self, ttl_seconds: Optional[int] = None, max_tasks: Optional[int] = None):
        """Initialize task manager"""
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = (
            ttl_seconds if ttl_seconds is not None
            else int(os.getenv("TASK_TTL_SECONDS", str(DEFAULT_TASK_TTL_SECONDS)))
        )
        self._max_tasks = (
            max_tasks if max_tasks is not None
            else int(os.getenv("TASK_MAX_COUNT", str(DEFAULT_MAX_TASKS)))
        )
        # Captured lazily so we can wake up SSE waiters from any thread via
        # call_soon_threadsafe, even if a mutation happens off the event loop thread.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _capture_loop(self) -> None:
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass  # Called from a non-asyncio context (e.g. a script); no loop to notify.

    def _signal_update(self, task: Task) -> None:
        """
        Wake up any SSE listeners waiting on this task's update_event. Thread-safe.

        The captured loop can already be closed by the time a worker thread gets here:
        audio generation runs for minutes, so a shutdown or restart mid-generation
        leaves background threads signalling into a dead loop. Never let that escape --
        this is called from set_task_error() too, where raising would mask the very
        error we are trying to record. With the loop gone there are no live waiters, so
        setting the flag directly is enough for anyone who reads it later.
        """
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(task.update_event.set)
                return
            except RuntimeError:
                logger.debug("Event loop closed; setting update_event for task %s directly", task.task_id)
        task.update_event.set()

    def _remove_task_locked(self, task_id: str) -> None:
        """Remove a task and its output directory. Caller must hold self._lock."""
        self.tasks.pop(task_id, None)
        task_dir = OUTPUTS_DIR / task_id
        if task_dir.exists():
            try:
                shutil.rmtree(task_dir, ignore_errors=True)
            except OSError as e:
                logger.warning("Failed to clean up output directory for evicted task %s: %s", task_id, e)

    def _evict_locked(self) -> None:
        """
        Evict TTL-expired tasks, then (if still over the cap) the oldest-updated
        remaining tasks. Caller must hold self._lock. Called lazily on every
        create/get rather than from a background thread.
        """
        now = datetime.now()
        ttl = timedelta(seconds=self._ttl_seconds)
        expired_ids = [tid for tid, task in self.tasks.items() if now - task.updated_at > ttl]
        for tid in expired_ids:
            logger.info("Evicting expired task %s (TTL %ds)", tid, self._ttl_seconds)
            self._remove_task_locked(tid)

        if len(self.tasks) > self._max_tasks:
            overflow = len(self.tasks) - self._max_tasks
            oldest_ids = sorted(self.tasks, key=lambda tid: self.tasks[tid].updated_at)[:overflow]
            for tid in oldest_ids:
                logger.info("Evicting task %s to stay under max task cap (%d)", tid, self._max_tasks)
                self._remove_task_locked(tid)

    def create_task(self, text_content: str) -> str:
        """Create a new task and return task_id"""
        self._capture_loop()
        with self._lock:
            task_id = str(uuid.uuid4())
            task = Task(task_id, text_content)
            self.tasks[task_id] = task
            # Evict after inserting (not before) so the cap is enforced against the
            # post-insert size — evicting first would let the dict grow to
            # max_tasks + 1 right after each creation.
            self._evict_locked()
            return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        with self._lock:
            self._evict_locked()
            return self.tasks.get(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int = None,
        message: str = None,
        total_segments: int = None,
        failed_segments: int = None
    ) -> bool:
        """Update task status"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.update_status(status, progress, message, total_segments, failed_segments)
        if task:
            self._signal_update(task)
            return True
        return False

    def set_task_error(self, task_id: str, error: str) -> bool:
        """Set task error"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.set_error(error)
        if task:
            self._signal_update(task)
            return True
        return False

    def set_task_files(self, task_id: str, audio_file: str = None, transcript_file: str = None) -> bool:
        """Set task output files"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                if audio_file:
                    task.audio_file = audio_file
                if transcript_file:
                    task.transcript_file = transcript_file
                task.updated_at = datetime.now()
        if task:
            self._signal_update(task)
            return True
        return False


# Singleton instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get or create task manager instance"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
