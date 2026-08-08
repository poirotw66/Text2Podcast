"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel
from typing import Optional, List, Tuple, Dict
from enum import Enum


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    STEP1 = "step1"  # Generating initial transcript
    STEP2 = "step2"  # Optimizing transcript
    STEP3 = "step3"  # Generating audio
    COMPLETED = "completed"
    FAILED = "failed"


class UploadRequest(BaseModel):
    """Request model for text upload"""
    text: str
    podcast_length_mode: Optional[str] = "MEDIUM"  # SHORT | MEDIUM | LONG


class UploadResponse(BaseModel):
    """Response model for upload"""
    task_id: str
    message: str


class Step1Request(BaseModel):
    """Request model for step 1 (generate initial transcript)"""
    podcast_length_mode: Optional[str] = "MEDIUM"  # SHORT | MEDIUM | LONG


class Step1Response(BaseModel):
    """Response model for step 1 (initial transcript)"""
    task_id: str
    initial_transcript: str
    message: str


class Step2Request(BaseModel):
    """Request model for step 2 (optimize transcript)"""
    task_id: str
    edited_transcript: Optional[str] = None  # Optional: user can edit before optimization


class Step2Response(BaseModel):
    """Response model for step 2 (optimized transcript)"""
    task_id: str
    optimized_transcript: List[Tuple[str, str]]  # List of (speaker, text) tuples
    message: str


class Step3Request(BaseModel):
    """Request model for step 3 (generate audio)"""
    final_transcript: Optional[List[Tuple[str, str]]] = None  # Optional: final transcript to use for audio generation
    voice_settings: Optional[Dict[str, str]] = None  # Optional: custom voice settings {"Speaker 1": "Kore", "Speaker 2": "Charon"}
    style_settings: Optional[Dict[str, str]] = None  # Optional: per-speaker TTS prompt, keyed like voice_settings
    #   {"Speaker 1": "Speak warmly and conversationally", "Speaker 2": "Speak with energy and curiosity"}
    # Unknown keys are ignored; missing speakers fall back to the module default prompt.
    # Each value is capped at 200 characters (enforced in the route).


class TaskStatusResponse(BaseModel):
    """Response model for task status"""
    task_id: str
    status: TaskStatus
    progress: int  # 0-100
    message: Optional[str] = None
    error: Optional[str] = None
    audio_file: Optional[str] = None
    transcript_file: Optional[str] = None
    total_segments: Optional[int] = None   # None until audio generation has run
    failed_segments: Optional[int] = None  # 0 when everything succeeded
    partial: bool = False                  # True iff failed_segments > 0


class ProgressEvent(BaseModel):
    """SSE progress event model"""
    task_id: str
    status: TaskStatus
    progress: int
    message: Optional[str] = None
    total_segments: Optional[int] = None   # None until audio generation has run
    failed_segments: Optional[int] = None  # 0 when everything succeeded
    partial: bool = False                  # True iff failed_segments > 0


class SegmentInfo(BaseModel):
    """Per-segment TTS state, as recorded in the task's metadata.json"""
    index: int          # 1-based, matches metadata ordering and filenames
    speaker: str
    text: str
    voice: str
    success: bool
    error: Optional[str] = None  # populated when success is False


class SegmentsResponse(BaseModel):
    """Response model for GET /api/segments/{task_id}"""
    total: int
    failed: int
    segments: List[SegmentInfo]


class RegenerateRequest(BaseModel):
    """Request model for POST /api/regenerate/{task_id}"""
    segment_index: int             # required, 1-based
    text: Optional[str] = None     # optional; reuses the existing text when omitted
    voice: Optional[str] = None    # optional; reuses the existing voice when omitted
    style_prompt: Optional[str] = None  # optional TTS style prompt for this segment only. Max 200 chars.

