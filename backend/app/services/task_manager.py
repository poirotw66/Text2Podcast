"""
Task manager for tracking job status and progress
"""
import uuid
from typing import Dict, Optional
from datetime import datetime
from app.models.schemas import TaskStatus


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
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def update_status(self, status: TaskStatus, progress: int = None, message: str = None):
        """Update task status"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if message:
            self.message = message
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
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class TaskManager:
    """In-memory task manager"""
    
    def __init__(self):
        """Initialize task manager"""
        self.tasks: Dict[str, Task] = {}
    
    def create_task(self, text_content: str) -> str:
        """Create a new task and return task_id"""
        task_id = str(uuid.uuid4())
        task = Task(task_id, text_content)
        self.tasks[task_id] = task
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int = None,
        message: str = None
    ) -> bool:
        """Update task status"""
        task = self.get_task(task_id)
        if task:
            task.update_status(status, progress, message)
            return True
        return False
    
    def set_task_error(self, task_id: str, error: str) -> bool:
        """Set task error"""
        task = self.get_task(task_id)
        if task:
            task.set_error(error)
            return True
        return False
    
    def set_task_files(self, task_id: str, audio_file: str = None, transcript_file: str = None) -> bool:
        """Set task output files"""
        task = self.get_task(task_id)
        if task:
            if audio_file:
                task.audio_file = audio_file
            if transcript_file:
                task.transcript_file = transcript_file
            task.updated_at = datetime.now()
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

