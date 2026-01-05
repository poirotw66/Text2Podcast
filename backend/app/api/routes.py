"""
API routes for podcast generation
"""
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from typing import Dict

from app.models.schemas import (
    UploadRequest, UploadResponse, TaskStatusResponse, TaskStatus, ProgressEvent,
    Step1Response, Step2Request, Step2Response, Step3Request
)
from app.services.task_manager import get_task_manager
from app.services.transcript_service import get_transcript_service
from app.services.audio_service import get_audio_service
from app.utils.file_handler import save_transcript, save_text_file

router = APIRouter(prefix="/api", tags=["podcast"])

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR = BASE_DIR / "uploads"


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
        
        transcript = transcript_service.generate_transcript(text_content)
        
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
        
        audio_result = audio_service.generate_audio_from_transcript(
            transcript, task_output_dir
        )
        
        if audio_result["success"] == 0:
            raise Exception("Failed to generate any audio files")
        
        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 90, "Merging audio files..."
        )
        
        # Merge audio files
        metadata_file = Path(audio_result["metadata_file"])
        merged_audio_file = task_output_dir / "merged_audio.mp3"
        
        merged_file = audio_service.merge_audio_files(
            metadata_file, merged_audio_file
        )
        
        if not merged_file:
            raise Exception("Failed to merge audio files")
        
        # Update task with final files
        task_manager.set_task_files(
            task_id,
            audio_file=str(merged_audio_file),
            transcript_file=str(transcript_file)
        )
        
        task_manager.update_task_status(
            task_id, TaskStatus.COMPLETED, 100, "Podcast generation completed!"
        )
        
    except Exception as e:
        task_manager.set_task_error(task_id, str(e))


@router.post("/upload", response_model=UploadResponse)
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


@router.post("/step1/{task_id}", response_model=Step1Response)
async def step1_generate_initial_transcript(task_id: str):
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
        
        # Only generate initial transcript (first step of transcript_service)
        llm_service = transcript_service.llm_service
        initial_transcript = llm_service.generate_initial_transcript(task.text_content)
        
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
        task_manager.set_task_error(task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate initial transcript: {str(e)}")


@router.post("/step2", response_model=Step2Response)
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
                from app.utils.file_handler import load_text_file
                transcript_to_optimize = load_text_file(initial_transcript_file)
            else:
                raise HTTPException(status_code=400, detail="No transcript available to optimize")
        
        # Optimize transcript
        llm_service = transcript_service.llm_service
        optimized_transcript = llm_service.optimize_transcript(transcript_to_optimize)
        
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
    except Exception as e:
        task_manager.set_task_error(request.task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to optimize transcript: {str(e)}")


@router.post("/step3/{task_id}", response_model=TaskStatusResponse)
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
            from app.utils.file_handler import load_transcript
            final_transcript = load_transcript(optimized_transcript_file)
        else:
            raise HTTPException(status_code=400, detail="No transcript available for audio generation")
    
    # Save final transcript
    task_output_dir = OUTPUTS_DIR / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    final_transcript_file = task_output_dir / "final_transcript.txt"
    save_transcript(final_transcript, final_transcript_file)
    
    # Start background audio generation
    background_tasks.add_task(process_audio_generation, task_id, final_transcript)
    
    return TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.STEP3,
        progress=0,
        message="Audio generation started"
    )


async def process_audio_generation(task_id: str, transcript: list):
    """Background task to generate audio from transcript"""
    task_manager = get_task_manager()
    audio_service = get_audio_service()
    
    try:
        task_output_dir = OUTPUTS_DIR / task_id
        
        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 30, "Generating audio files..."
        )
        
        audio_result = audio_service.generate_audio_from_transcript(
            transcript, task_output_dir
        )
        
        if audio_result["success"] == 0:
            raise Exception("Failed to generate any audio files")
        
        task_manager.update_task_status(
            task_id, TaskStatus.STEP3, 80, "Merging audio files..."
        )
        
        # Merge audio files
        metadata_file = Path(audio_result["metadata_file"])
        merged_audio_file = task_output_dir / "merged_audio.mp3"
        
        merged_file = audio_service.merge_audio_files(
            metadata_file, merged_audio_file
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
        
        task_manager.update_task_status(
            task_id, TaskStatus.COMPLETED, 100, "Podcast generation completed!"
        )
        
    except Exception as e:
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
        transcript_file=task.transcript_file
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
        OUTPUTS_DIR / task_id / "initial_transcript.txt"
    ]
    
    for transcript_path in transcript_paths:
        if transcript_path and transcript_path.exists():
            try:
                from app.utils.file_handler import load_transcript, load_text_file
                # Try to load as structured transcript first
                try:
                    transcript = load_transcript(transcript_path)
                    if isinstance(transcript, list) and len(transcript) > 0:
                        return {"transcript": transcript}
                except:
                    # If that fails, try as plain text
                    content = load_text_file(transcript_path)
                    # Try to parse as Python list
                    try:
                        import ast
                        parsed = ast.literal_eval(content.strip())
                        if isinstance(parsed, list):
                            return {"transcript": parsed}
                    except:
                        pass
                    # Return as plain text if parsing fails
                    return {"transcript": [("Speaker 1", content)]}
            except Exception as e:
                continue
    
    raise HTTPException(status_code=404, detail="Transcript not found")


@router.get("/stream/{task_id}")
async def stream_progress(task_id: str):
    """SSE stream for task progress"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        last_progress = -1
        last_status = None
        
        # Send initial status immediately
        task = task_manager.get_task(task_id)
        if task:
            event = ProgressEvent(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress,
                message=task.message or "Initializing..."
            )
            yield {
                "event": "progress",
                "data": event.model_dump_json()
            }
            last_progress = task.progress
            last_status = task.status
        
        while True:
            task = task_manager.get_task(task_id)
            if not task:
                break
            
            # Check if status or progress changed
            status_changed = task.status != last_status
            progress_changed = task.progress != last_progress
            
            if status_changed or progress_changed:
                event = ProgressEvent(
                    task_id=task.task_id,
                    status=task.status,
                    progress=task.progress,
                    message=task.message
                )
                # SSE format: data: {...}\n\n
                yield {
                    "event": "progress",
                    "data": event.model_dump_json()
                }
                last_progress = task.progress
                last_status = task.status
            
            # Stop if completed or failed
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Send final event if not already sent
                if task.status != last_status or task.progress != last_progress:
                    event = ProgressEvent(
                        task_id=task.task_id,
                        status=task.status,
                        progress=task.progress,
                        message=task.message or (task.error if task.status == TaskStatus.FAILED else "Completed")
                    )
                    yield {
                        "event": "progress",
                        "data": event.model_dump_json()
                    }
                break
            
            await asyncio.sleep(1)  # Check every 1 second
    
    return EventSourceResponse(event_generator())

