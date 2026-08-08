"""
API routes for podcast generation
"""
import asyncio
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Header, Request
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import (
    UploadRequest, UploadResponse, TaskStatusResponse, TaskStatus, ProgressEvent,
    Step1Request, Step1Response, Step2Request, Step2Response, Step3Request,
    SegmentInfo, SegmentsResponse, RegenerateRequest
)
from app.services.task_manager import get_task_manager, Task
from app.services.transcript_service import get_transcript_service
from app.services.audio_service import get_audio_service
from app.utils.file_handler import (
    save_transcript, save_text_file, load_transcript, load_text_file, load_metadata
)

# Per section 3 of the API contract: style_settings values (and the regenerate
# endpoint's style_prompt) are capped at this many characters.
MAX_STYLE_PROMPT_LENGTH = 200

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["podcast"])

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR = BASE_DIR / "uploads"


# ---------------------------------------------------------------------------
# Abuse protection: optional shared-secret auth + simple per-IP rate limiting.
# Applied only to the expensive/mutating endpoints (upload, step1-3); /health is
# never gated. If API_KEY is unset, auth is a no-op so local dev is unaffected.
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY")
RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))

# Per-client-IP sliding window of request timestamps. Simple and in-process by
# design (matches the single-process TaskManager constraint) — not shared across
# workers/processes and never evicts idle IPs, which is an acceptable tradeoff for
# a basic abuse guard but would need revisiting for a large, long-running deployment.
_rate_limit_hits: Dict[str, deque] = defaultdict(deque)


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    hits = _rate_limit_hits[client_ip]
    while hits and now - hits[0] > RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    hits.append(now)


async def enforce_abuse_protection(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """
    Dependency applied to expensive/mutating endpoints:
    - If API_KEY is set, requires a matching X-API-Key header (constant-time compare).
    - Always applies a simple per-client-IP rate limit.
    """
    if API_KEY:
        if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
            raise HTTPException(status_code=401, detail="Missing or invalid API key")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)


async def process_podcast_task(task_id: str, text_content: str):
    """
    Background task to process podcast generation

    Steps:
    1. Generate initial transcript (30%)
    2. Optimize transcript (60%)
    3. Generate audio (90%)
    4. Merge audio (100%)
    """
    task_manager = get_task_manager()
    transcript_service = get_transcript_service()
    audio_service = get_audio_service()

    try:
        # Update to processing status
        task_manager.update_task_status(
            task_id, TaskStatus.PROCESSING, 10, "Starting podcast generation..."
        )
        await asyncio.sleep(0.5)  # Give SSE time to send initial status

        # Step 1: Generate initial transcript
        task_manager.update_task_status(
            task_id, TaskStatus.STEP1, 30, "Generating initial transcript..."
        )
        await asyncio.sleep(0.5)

        # transcript_service.generate_transcript() makes synchronous OpenAI calls;
        # run it off the event loop so it doesn't block every other request/SSE stream.
        transcript = await asyncio.to_thread(transcript_service.generate_transcript, text_content)

        # Save transcript
        task_output_dir = OUTPUTS_DIR / task_id
        transcript_file = task_output_dir / "transcript.txt"
        save_transcript(transcript, transcript_file)

        task_manager.set_task_files(task_id, transcript_file=str(transcript_file))
        task_manager.update_task_status(
            task_id, TaskStatus.STEP2, 60, "Transcript generated, optimizing..."
        )
        await asyncio.sleep(0.5)

        # Step 2 is already done in transcript_service.generate_transcript
        # So we move to Step 3

        # Step 3: Generate audio
        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 70, "Generating audio files..."
        )
        await asyncio.sleep(0.5)

        # generate_audio_from_transcript is synchronous (it manages its own
        # ThreadPoolExecutor internally for parallel TTS calls) — run the whole call
        # in a worker thread so it doesn't block the event loop.
        audio_result = await asyncio.to_thread(
            audio_service.generate_audio_from_transcript, transcript, task_output_dir
        )

        if audio_result["success"] == 0:
            raise Exception("Failed to generate any audio files")

        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 90, "Merging audio files..."
        )

        # Merge audio files
        metadata_file = Path(audio_result["metadata_file"])
        merged_audio_file = task_output_dir / "merged_audio.mp3"

        merged_file = await asyncio.to_thread(
            audio_service.merge_audio_files, metadata_file, merged_audio_file
        )

        if not merged_file:
            raise Exception("Failed to merge audio files")

        # Update task with final files
        task_manager.set_task_files(
            task_id,
            audio_file=str(merged_audio_file),
            transcript_file=str(transcript_file)
        )

        total_segments = audio_result["success"] + audio_result["failed"]
        failed_segments = audio_result["failed"]
        completion_message = (
            f"Podcast generation completed, but {failed_segments} of {total_segments} segments failed"
            if failed_segments else "Podcast generation completed!"
        )
        task_manager.update_task_status(
            task_id, TaskStatus.COMPLETED, 100, completion_message,
            total_segments=total_segments, failed_segments=failed_segments
        )

    except Exception as e:
        logger.exception("process_podcast_task failed for task %s", task_id)
        task_manager.set_task_error(task_id, str(e))


@router.post("/upload", response_model=UploadResponse, dependencies=[Depends(enforce_abuse_protection)])
async def upload_text(request: UploadRequest):
    """Upload text content and create task (Step 0)"""
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text content cannot be empty")

    task_manager = get_task_manager()
    task_id = task_manager.create_task(request.text)

    return UploadResponse(
        task_id=task_id,
        message="Task created successfully"
    )


@router.post("/step1/{task_id}", response_model=Step1Response, dependencies=[Depends(enforce_abuse_protection)])
async def step1_generate_initial_transcript(task_id: str, request: Step1Request):
    """Step 1: Generate initial podcast transcript from text"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    transcript_service = get_transcript_service()

    try:
        task_manager.update_task_status(
            task_id, TaskStatus.STEP1, 30, "Generating initial transcript..."
        )

        # Get podcast length mode from request, default to MEDIUM
        podcast_length_mode = request.podcast_length_mode or "MEDIUM"

        # Only generate initial transcript (first step of transcript_service).
        # This is a synchronous OpenAI call — offload it so it doesn't block the loop.
        llm_service = transcript_service.llm_service
        initial_transcript = await asyncio.to_thread(
            llm_service.generate_initial_transcript,
            task.text_content,
            podcast_length_mode=podcast_length_mode,
        )

        # Save initial transcript
        task_output_dir = OUTPUTS_DIR / task_id
        task_output_dir.mkdir(parents=True, exist_ok=True)
        initial_transcript_file = task_output_dir / "initial_transcript.txt"
        save_text_file(initial_transcript, initial_transcript_file)

        task_manager.set_task_files(task_id, transcript_file=str(initial_transcript_file))
        task_manager.update_task_status(
            task_id, TaskStatus.STEP1, 100, "Initial transcript generated"
        )

        return Step1Response(
            task_id=task_id,
            initial_transcript=initial_transcript,
            message="Initial transcript generated successfully"
        )
    except Exception as e:
        logger.exception("Step 1 failed for task %s", task_id)
        task_manager.set_task_error(task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate initial transcript: {str(e)}")


@router.post("/step2", response_model=Step2Response, dependencies=[Depends(enforce_abuse_protection)])
async def step2_optimize_transcript(request: Step2Request):
    """Step 2: Optimize transcript for TTS (user can edit before optimization)"""
    task_manager = get_task_manager()
    task = task_manager.get_task(request.task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    transcript_service = get_transcript_service()

    try:
        task_manager.update_task_status(
            request.task_id, TaskStatus.STEP2, 50, "Optimizing transcript..."
        )

        # Use edited transcript if provided, otherwise use initial transcript
        if request.edited_transcript:
            transcript_to_optimize = request.edited_transcript
        else:
            # Load initial transcript
            initial_transcript_file = Path(task.transcript_file) if task.transcript_file else None
            if initial_transcript_file and initial_transcript_file.exists():
                transcript_to_optimize = load_text_file(initial_transcript_file)
            else:
                raise HTTPException(status_code=400, detail="No transcript available to optimize")

        # Optimize transcript. Synchronous OpenAI call — offload it so it doesn't
        # block the loop.
        llm_service = transcript_service.llm_service
        optimized_transcript = await asyncio.to_thread(
            llm_service.optimize_transcript, transcript_to_optimize
        )

        # Save optimized transcript
        task_output_dir = OUTPUTS_DIR / request.task_id
        optimized_transcript_file = task_output_dir / "optimized_transcript.txt"
        save_transcript(optimized_transcript, optimized_transcript_file)

        task_manager.set_task_files(request.task_id, transcript_file=str(optimized_transcript_file))
        task_manager.update_task_status(
            request.task_id, TaskStatus.STEP2, 100, "Transcript optimized"
        )

        return Step2Response(
            task_id=request.task_id,
            optimized_transcript=optimized_transcript,
            message="Transcript optimized successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Step 2 failed for task %s", request.task_id)
        task_manager.set_task_error(request.task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to optimize transcript: {str(e)}")


@router.post("/step3/{task_id}", response_model=TaskStatusResponse, dependencies=[Depends(enforce_abuse_protection)])
async def step3_generate_audio(task_id: str, request: Step3Request, background_tasks: BackgroundTasks):
    """Step 3: Generate audio from final transcript (only after user confirmation)"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Use provided final transcript or load from task
    if request and request.final_transcript:
        final_transcript = request.final_transcript
    else:
        # Load optimized transcript
        optimized_transcript_file = Path(task.transcript_file) if task.transcript_file else None
        if optimized_transcript_file and optimized_transcript_file.exists():
            final_transcript = load_transcript(optimized_transcript_file)
        else:
            raise HTTPException(status_code=400, detail="No transcript available for audio generation")

    # Save final transcript
    task_output_dir = OUTPUTS_DIR / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    final_transcript_file = task_output_dir / "final_transcript.txt"
    save_transcript(final_transcript, final_transcript_file)

    # Get voice settings from request or use defaults
    voice_settings = None
    if request and request.voice_settings:
        voice_settings = request.voice_settings
        logger.debug("Received voice settings for task %s: %s", task_id, voice_settings)
    else:
        logger.debug("No voice settings provided for task %s, using defaults", task_id)

    # Get style settings from request, validating the per-speaker prompt length cap.
    style_settings = None
    if request and request.style_settings:
        for speaker, style_prompt in request.style_settings.items():
            if len(style_prompt) > MAX_STYLE_PROMPT_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"style_settings[{speaker!r}] exceeds {MAX_STYLE_PROMPT_LENGTH} characters"
                )
        style_settings = request.style_settings
        logger.debug("Received style settings for task %s: %s", task_id, style_settings)
    else:
        logger.debug("No style settings provided for task %s, using defaults", task_id)

    # Start background audio generation
    background_tasks.add_task(
        process_audio_generation, task_id, final_transcript, voice_settings, style_settings
    )

    return TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.STEP3,
        progress=0,
        message="Audio generation started"
    )


async def process_audio_generation(
    task_id: str,
    transcript: list,
    voice_settings: Optional[Dict[str, str]] = None,
    style_settings: Optional[Dict[str, str]] = None
):
    """Background task to generate audio from transcript"""
    task_manager = get_task_manager()
    audio_service = get_audio_service()

    try:
        task_output_dir = OUTPUTS_DIR / task_id

        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 30, "Generating audio files..."
        )

        if voice_settings:
            logger.debug("Using voice settings in audio generation for task %s: %s", task_id, voice_settings)
        else:
            logger.debug("Using default voice settings in audio generation for task %s", task_id)

        if style_settings:
            logger.debug("Using style settings in audio generation for task %s: %s", task_id, style_settings)
        else:
            logger.debug("Using default style settings in audio generation for task %s", task_id)

        # Both generate_audio_from_transcript (synchronous; runs its own
        # ThreadPoolExecutor internally) and merge_audio_files (synchronous; shells
        # out to ffmpeg and waits) block. This function is awaited by FastAPI's
        # BackgroundTasks on the event loop, so without asyncio.to_thread these calls
        # would stall every other request and SSE stream on the server while they run.
        audio_result = await asyncio.to_thread(
            audio_service.generate_audio_from_transcript,
            transcript, task_output_dir, voice_settings=voice_settings, style_settings=style_settings
        )

        if audio_result["success"] == 0:
            raise Exception("Failed to generate any audio files")

        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 80, "Merging audio files..."
        )

        # Merge audio files
        metadata_file = Path(audio_result["metadata_file"])
        merged_audio_file = task_output_dir / "merged_audio.mp3"

        merged_file = await asyncio.to_thread(
            audio_service.merge_audio_files, metadata_file, merged_audio_file
        )

        if not merged_file:
            raise Exception("Failed to merge audio files")

        # Update task with final files
        final_transcript_file = task_output_dir / "final_transcript.txt"
        task_manager.set_task_files(
            task_id,
            audio_file=str(merged_audio_file),
            transcript_file=str(final_transcript_file)
        )

        total_segments = audio_result["success"] + audio_result["failed"]
        failed_segments = audio_result["failed"]
        completion_message = (
            f"Podcast generation completed, but {failed_segments} of {total_segments} segments failed"
            if failed_segments else "Podcast generation completed!"
        )
        task_manager.update_task_status(
            task_id, TaskStatus.COMPLETED, 100, completion_message,
            total_segments=total_segments, failed_segments=failed_segments
        )

    except Exception as e:
        logger.exception("process_audio_generation failed for task %s", task_id)
        task_manager.set_task_error(task_id, str(e))


@router.get("/segments/{task_id}", response_model=SegmentsResponse)
async def get_segments(task_id: str):
    """
    Get per-segment TTS state for a task, read from its metadata.json.

    404s distinctly for an unknown task vs. a known task where audio generation
    hasn't run yet (no metadata.json).
    """
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    metadata_file = OUTPUTS_DIR / task_id / "metadata.json"
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Audio generation has not run for this task yet")

    metadata = load_metadata(metadata_file)
    audio_files = sorted(metadata.get("audio_files", []), key=lambda item: item["index"])

    segments = [
        SegmentInfo(
            index=item["index"],
            speaker=item["speaker"],
            text=item["text"],
            voice=item["voice"],
            # Old metadata files predate the "success" key -- everything they recorded
            # was, by construction, a successful segment.
            success=item.get("success", True),
            error=item.get("error")
        )
        for item in audio_files
    ]
    failed = sum(1 for segment in segments if not segment.success)
    total = metadata.get("total_segments", len(segments))

    return SegmentsResponse(total=total, failed=failed, segments=segments)


@router.post(
    "/regenerate/{task_id}", response_model=TaskStatusResponse,
    dependencies=[Depends(enforce_abuse_protection)]
)
async def regenerate_segment(task_id: str, request: RegenerateRequest, background_tasks: BackgroundTasks):
    """
    Regenerate exactly one TTS segment, then re-merge the full audio.

    The work runs in the background (same pattern as /step3); the client follows
    /api/stream/{task_id} as usual and re-reads /api/segments/{task_id} or
    /api/status/{task_id} once it settles.
    """
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_output_dir = OUTPUTS_DIR / task_id
    metadata_file = task_output_dir / "metadata.json"
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Audio generation has not run for this task yet")

    metadata = load_metadata(metadata_file)
    total_segments = metadata.get("total_segments", len(metadata.get("audio_files", [])))

    if request.segment_index < 1 or request.segment_index > total_segments:
        raise HTTPException(
            status_code=400,
            detail=f"segment_index must be between 1 and {total_segments}"
        )

    if request.style_prompt is not None and len(request.style_prompt) > MAX_STYLE_PROMPT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"style_prompt exceeds {MAX_STYLE_PROMPT_LENGTH} characters"
        )

    background_tasks.add_task(
        process_regenerate_segment,
        task_id, request.segment_index, request.text, request.voice, request.style_prompt
    )

    return TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.STEP3,
        progress=0,
        message="Segment regeneration started"
    )


async def process_regenerate_segment(
    task_id: str,
    segment_index: int,
    text: Optional[str],
    voice: Optional[str],
    style_prompt: Optional[str]
):
    """Background task: regenerate one segment's audio, then re-merge the full file."""
    task_manager = get_task_manager()
    audio_service = get_audio_service()
    task_output_dir = OUTPUTS_DIR / task_id
    metadata_file = task_output_dir / "metadata.json"

    try:
        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 30, f"Regenerating segment {segment_index}..."
        )

        # regenerate_segment (synchronous: one TTS call) and merge_audio_files
        # (synchronous: shells out to ffmpeg) both block, so run them off the event
        # loop the same way the initial generation does.
        regen_result = await asyncio.to_thread(
            audio_service.regenerate_segment,
            metadata_file, segment_index, text, voice, style_prompt
        )

        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 70, "Merging audio files..."
        )

        merged_audio_file = task_output_dir / "merged_audio.mp3"
        merged_file = await asyncio.to_thread(
            audio_service.merge_audio_files, metadata_file, merged_audio_file
        )

        if not merged_file:
            raise Exception("Failed to merge audio files")

        task_manager.set_task_files(task_id, audio_file=str(merged_audio_file))

        total_segments = regen_result["total_segments"]
        failed_segments = regen_result["failed"]
        completion_message = (
            f"Segment regeneration completed, but {failed_segments} of {total_segments} segments failed"
            if failed_segments else "Segment regeneration completed successfully"
        )
        task_manager.update_task_status(
            task_id, TaskStatus.COMPLETED, 100, completion_message,
            total_segments=total_segments, failed_segments=failed_segments
        )

    except Exception as e:
        logger.exception("process_regenerate_segment failed for task %s (segment %d)", task_id, segment_index)
        task_manager.set_task_error(task_id, str(e))


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get task status"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        error=task.error,
        audio_file=task.audio_file,
        transcript_file=task.transcript_file,
        total_segments=task.total_segments,
        failed_segments=task.failed_segments,
        partial=task.partial
    )


@router.get("/download/{task_id}/audio")
async def download_audio(task_id: str):
    """Download generated audio file"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.audio_file:
        raise HTTPException(status_code=404, detail="Audio file not available")

    audio_path = Path(task.audio_file)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=f"podcast_{task_id}.mp3"
    )


@router.get("/download/{task_id}/transcript")
async def download_transcript(task_id: str):
    """Download transcript file"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.transcript_file:
        raise HTTPException(status_code=404, detail="Transcript file not available")

    transcript_path = Path(task.transcript_file)
    if not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript file not found")

    return FileResponse(
        path=transcript_path,
        media_type="text/plain",
        filename=f"transcript_{task_id}.txt"
    )


@router.get("/transcript/{task_id}")
async def get_transcript(task_id: str):
    """Get transcript content as JSON"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Try to load final transcript first, then optimized, then initial
    transcript_paths = [
        Path(task.transcript_file) if task.transcript_file else None,
        OUTPUTS_DIR / task_id / "final_transcript.txt",
        OUTPUTS_DIR / task_id / "optimized_transcript.txt",
        OUTPUTS_DIR / task_id / "initial_transcript.txt",
    ]

    for transcript_path in transcript_paths:
        if not transcript_path or not transcript_path.exists():
            continue

        # Structured transcripts (final/optimized) parse via the shared JSON/legacy
        # loader. initial_transcript.txt is plain prose at this stage in the pipeline
        # (not yet split into speaker turns), so it's expected to fail that parse —
        # in that case fall back to returning it as a single untagged segment.
        try:
            transcript = load_transcript(transcript_path)
        except ValueError:
            try:
                content = load_text_file(transcript_path)
            except OSError as read_error:
                logger.warning("Failed to read transcript file %s: %s", transcript_path, read_error)
                continue
            return {"transcript": [("Speaker 1", content)]}

        if transcript:
            return {"transcript": transcript}

    raise HTTPException(status_code=404, detail="Transcript not found")


@router.get("/stream/{task_id}")
async def stream_progress(task_id: str, request: Request):
    """
    SSE stream for task progress.

    Waits on the task's asyncio.Event (set by TaskManager on every update) instead of
    polling the task dict on a fixed interval, detects client disconnects so
    abandoned connections don't linger, caps total stream lifetime so a wedged task
    can't hold a connection open forever, and sends periodic keep-alive comments so
    intermediary proxies don't close the connection for being idle.
    """
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stream_timeout_seconds = float(os.getenv("SSE_STREAM_TIMEOUT_SECONDS", "1800"))  # 30 minutes
    keepalive_interval_seconds = float(os.getenv("SSE_KEEPALIVE_INTERVAL_SECONDS", "15"))

    def _progress_event(current: Task) -> dict:
        return {
            "event": "progress",
            "data": ProgressEvent(
                task_id=current.task_id,
                status=current.status,
                progress=current.progress,
                message=current.message or (current.error if current.status == TaskStatus.FAILED else None),
                total_segments=current.total_segments,
                failed_segments=current.failed_segments,
                partial=current.partial
            ).model_dump_json(),
        }

    async def event_generator():
        stream_start = time.monotonic()
        last_progress = -1
        last_status = None

        # Send initial status immediately
        current = task_manager.get_task(task_id)
        if not current:
            return
        yield _progress_event(current)
        last_progress, last_status = current.progress, current.status
        if current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return

        while True:
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE stream for task %s", task_id)
                return

            if time.monotonic() - stream_start > stream_timeout_seconds:
                logger.warning(
                    "SSE stream for task %s exceeded %.0fs timeout; closing", task_id, stream_timeout_seconds
                )
                return

            current = task_manager.get_task(task_id)
            if not current:
                return

            try:
                await asyncio.wait_for(current.update_event.wait(), timeout=keepalive_interval_seconds)
                current.update_event.clear()
            except asyncio.TimeoutError:
                # No update within the keep-alive window — send a comment (not a data
                # event) purely to keep intermediary proxies from treating this
                # connection as idle and closing it.
                yield {"comment": "keep-alive"}
                continue

            current = task_manager.get_task(task_id)
            if not current:
                return

            status_changed = current.status != last_status
            progress_changed = current.progress != last_progress
            if status_changed or progress_changed:
                yield _progress_event(current)
                last_progress, last_status = current.progress, current.status

            if current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return

    return EventSourceResponse(event_generator())
