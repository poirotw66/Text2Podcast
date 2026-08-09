"""
Audio generation service using Gemini TTS
Integrates functionality from generate_audio_gemini.py
"""
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from google.cloud import texttospeech
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Thread-local storage for client
_thread_local = threading.local()

# Default voices, used whenever a request doesn't supply its own voice_settings.
# This is intentionally read-only: it used to be a module-level dict mutated in place
# by set_voice_settings(), which meant one request's voice choice could leak into (or
# get clobbered by) a concurrent request's audio generation. Voice settings are now
# threaded through generate_audio_from_transcript() as a per-call argument instead.
DEFAULT_SPEAKER_VOICES: Dict[str, str] = {
    "Speaker 1": "Kore",
    "Speaker 2": "Charon"
}

# Default TTS steerability prompt, used whenever a request doesn't supply its own
# style_settings (or supplies settings that don't cover a given speaker). Like
# DEFAULT_SPEAKER_VOICES above, style settings are threaded through
# generate_audio_from_transcript() as a per-call argument rather than a mutable
# module global, for the same concurrency reason.
DEFAULT_TTS_PROMPT = "Say the following naturally"

# TTS configuration
#
# The Cloud TTS model is passed as VoiceSelectionParams.model_name. Override it
# with the TTS_MODEL env var so moving between model generations needs no code
# change -- the voice names and language code are independent of it.
#
# gemini-3.1-flash-tts-preview is the current 3.x TTS model. It is a *preview*
# model: the identifier can change or be withdrawn, so TTS_MODEL is the escape
# hatch back to the GA gemini-2.5-flash-tts if it misbehaves.
#
# NOTE: not verified against a live API -- no credentials in this environment.
DEFAULT_TTS_MODEL = "gemini-3.1-flash-tts-preview"
TTS_MODEL = os.getenv("TTS_MODEL", DEFAULT_TTS_MODEL)
AUDIO_FORMAT = "mp3"
LANGUAGE_CODE = "cmn-tw"

# Audio encoding mapping
AUDIO_ENCODING_MAP = {
    "mp3": texttospeech.AudioEncoding.MP3,
    "linear16": texttospeech.AudioEncoding.LINEAR16,
    "ogg_opus": texttospeech.AudioEncoding.OGG_OPUS,
    "alaw": texttospeech.AudioEncoding.ALAW,
    "mulaw": texttospeech.AudioEncoding.MULAW,
}


def get_client() -> texttospeech.TextToSpeechClient:
    """Get Google Cloud Text-to-Speech client (thread-safe)"""
    if not hasattr(_thread_local, 'client'):
        _thread_local.client = texttospeech.TextToSpeechClient()
    return _thread_local.client


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable"""
    error_str = str(error).lower()

    retryable_keywords = [
        "timeout", "connection", "rate limit", "quota", "temporary",
        "503", "500", "429", "502", "504"
    ]

    non_retryable_keywords = [
        "sensitive", "harmful content", "invalid", "permission denied",
        "not found", "disabled", "400"
    ]

    for keyword in non_retryable_keywords:
        if keyword in error_str:
            return False

    for keyword in retryable_keywords:
        if keyword in error_str:
            return True

    return False


def generate_single_audio(
    text: str,
    voice: str,
    output_file: Path,
    model: str = TTS_MODEL,
    language_code: str = LANGUAGE_CODE,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    prompt: str = DEFAULT_TTS_PROMPT
) -> Dict:
    """
    Generate a single audio file using Gemini TTS

    Args:
        text: Text to convert
        voice: Voice name (e.g., "Kore", "Charon")
        output_file: Output file path
        model: TTS model
        language_code: Language code
        max_retries: Maximum retries
        retry_delay: Delay between retries
        prompt: TTS steerability prompt passed as SynthesisInput.prompt (e.g. "Speak
            warmly and conversationally"). Defaults to DEFAULT_TTS_PROMPT.

    Returns:
        Dictionary with success status and file info
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            client = get_client()

            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(
                text=text,
                prompt=prompt
            )

            # Select voice
            voice_selection = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice,
                model_name=model
            )

            # Configure audio output
            audio_encoding = AUDIO_ENCODING_MAP.get(AUDIO_FORMAT.lower(), texttospeech.AudioEncoding.MP3)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding
            )

            # Perform TTS request
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_selection,
                audio_config=audio_config
            )

            # Save audio file
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "wb") as out:
                out.write(response.audio_content)

            return {
                "success": True,
                "file": str(output_file),
                "text": text,
                "voice": voice
            }

        except Exception as e:
            last_error = e
            if attempt < max_retries and is_retryable_error(e):
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                return {
                    "success": False,
                    "error": str(e),
                    "text": text
                }

    return {
        "success": False,
        "error": str(last_error) if last_error else "Unknown error",
        "text": text
    }


def _require_ffmpeg() -> str:
    """
    Locate the ffmpeg binary, failing loudly if it isn't installed.

    ffmpeg was already a hard runtime dependency of pydub (pydub just shells out to
    it), so requiring it directly here removes a Python dependency rather than
    adding one.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg binary not found on PATH. Install ffmpeg to merge audio segments "
            "(e.g. `apt-get install ffmpeg` or `brew install ffmpeg`)."
        )
    return ffmpeg_path


def _concat_list_entry(path: Path) -> str:
    """Format a path as a `file '...'` line for an ffmpeg concat-demuxer list file."""
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def _generate_silence_file(ffmpeg_path: str, duration_ms: int, output_path: Path) -> None:
    """Render `duration_ms` of silence to `output_path` as an mp3 via ffmpeg's anullsrc."""
    cmd = [
        ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(max(duration_ms, 0) / 1000.0),
        "-c:a", "libmp3lame", "-q:a", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to generate silence segment: {result.stderr}")


class AudioService:
    """Service for generating audio from transcript"""

    def __init__(self):
        """Initialize audio service"""
        pass

    def generate_audio_from_transcript(
        self,
        transcript: List[Tuple[str, str]],
        output_dir: Path,
        max_workers: int = 5,
        voice_settings: Optional[Dict[str, str]] = None,
        style_settings: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Dict:
        """
        Generate audio files from transcript

        Args:
            transcript: List of (speaker, text) tuples
            output_dir: Output directory
            max_workers: Number of parallel workers
            voice_settings: Optional voice settings dict (e.g., {"Speaker 1": "Kore", "Speaker 2": "Charon"}).
                Falls back to DEFAULT_SPEAKER_VOICES when not provided. This is a per-call
                argument (not shared mutable state), so concurrent requests with different
                voice choices can't clobber each other.
            style_settings: Optional per-speaker TTS prompt dict (e.g.
                {"Speaker 1": "Speak warmly and conversationally"}), keyed exactly like
                voice_settings. Unknown keys are ignored; speakers missing from the dict
                fall back to DEFAULT_TTS_PROMPT. Also a per-call argument, for the same
                concurrency reason as voice_settings.
            model: Optional TTS model override; defaults to the module-level TTS_MODEL.
                Per-call for the same reason as the settings above -- callers that need a
                different model must not have to reassign the module constant.
            language_code: Optional language override; defaults to LANGUAGE_CODE.

        Returns:
            Dictionary with audio files info and metadata
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        effective_model = model if model is not None else TTS_MODEL
        effective_language = language_code if language_code is not None else LANGUAGE_CODE

        # Use provided voice/style settings or fall back to defaults
        voices_to_use = voice_settings if voice_settings else DEFAULT_SPEAKER_VOICES
        styles_to_use = style_settings if style_settings else {}

        logger.info("Voice mapping: %s", voices_to_use)

        # Helper function to normalize speaker name (handle both English and Chinese)
        def get_voice_for_speaker(speaker_name: str) -> str:
            """Get voice for speaker, handling both English and Chinese speaker names"""
            # Try exact match first
            if speaker_name in voices_to_use:
                return voices_to_use[speaker_name]

            # Try to match by extracting speaker number
            # Handle formats like "Speaker 1", "講者 1", "Speaker1", "講者1", etc.
            match = re.search(r'[12]', speaker_name)
            if match:
                speaker_num = match.group()
                # Map to English key format
                english_key = f"Speaker {speaker_num}"
                if english_key in voices_to_use:
                    return voices_to_use[english_key]

            # Default fallback
            return "Kore"

        def get_style_for_speaker(speaker_name: str) -> str:
            """Get TTS prompt for speaker, mirroring get_voice_for_speaker's matching rules"""
            if speaker_name in styles_to_use:
                return styles_to_use[speaker_name]

            match = re.search(r'[12]', speaker_name)
            if match:
                speaker_num = match.group()
                english_key = f"Speaker {speaker_num}"
                if english_key in styles_to_use:
                    return styles_to_use[english_key]

            return DEFAULT_TTS_PROMPT

        # Prepare tasks
        tasks = []
        for i, (speaker, text) in enumerate(transcript, 1):
            voice = get_voice_for_speaker(speaker)
            style_prompt = get_style_for_speaker(speaker)
            logger.debug("Segment %d: Speaker '%s' -> Voice '%s'", i, speaker, voice)
            output_file = output_dir / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
            tasks.append({
                "index": i,
                "speaker": speaker,
                "text": text,
                "voice": voice,
                "prompt": style_prompt,
                "output_file": output_file
            })

        # Generate audio in parallel
        audio_files = []
        success_count = 0
        fail_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(
                    generate_single_audio,
                    task["text"],
                    task["voice"],
                    task["output_file"],
                    model=effective_model,
                    language_code=effective_language,
                    prompt=task["prompt"]
                ): task for task in tasks
            }

            results = {}
            for future in as_completed(future_to_task):
                result = future.result()
                task = future_to_task[future]
                results[task["index"]] = result

        # Sort and process results. Every segment is recorded here in index order --
        # successful and failed alike -- so downstream consumers (the segments API,
        # regeneration) can identify exactly which indices failed. Only the "file" path
        # of a *successful* segment actually exists on disk; merge_audio_files() relies
        # on that (plus the "success" flag) to skip failures during the merge.
        for index in sorted(results.keys()):
            result = results[index]
            task = tasks[index - 1]
            entry = {
                "speaker": task["speaker"],
                "index": index,
                "file": str(task["output_file"]),
                "text": task["text"],
                "voice": task["voice"],
                "success": result["success"],
                "error": None if result["success"] else result.get("error")
            }
            audio_files.append(entry)
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
                logger.error("Failed to generate audio for segment %d: %s", index, result.get("error"))

        # Save metadata
        metadata_file = output_dir / "metadata.json"
        metadata = {
            "total_segments": len(transcript),
            "success": success_count,
            "failed": fail_count,
            "model_used": effective_model,
            "language_code": effective_language,
            "audio_files": audio_files
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {
            "success": success_count,
            "failed": fail_count,
            "audio_files": audio_files,
            "metadata_file": str(metadata_file),
            "output_dir": str(output_dir)
        }

    def merge_audio_files(
        self,
        metadata_file: Path,
        output_file: Path,
        silence_duration_ms: int = 500
    ) -> Optional[Path]:
        """
        Merge all audio files into one, in metadata order, with `silence_duration_ms`
        of silence inserted between consecutive segments.

        Uses ffmpeg's concat demuxer directly via subprocess instead of pydub (which
        is unmaintained and depends on the stdlib `audioop` module removed in Python
        3.13). ffmpeg was already pydub's runtime dependency for this, so this removes
        a dependency rather than adding one. Never invoked with shell=True — all
        arguments are passed as an argv list.

        Args:
            metadata_file: Path to metadata.json
            output_file: Output merged file path
            silence_duration_ms: Silence duration between segments

        Returns:
            Path to merged file or None if failed
        """
        ffmpeg_path = _require_ffmpeg()

        # Read metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        audio_files = metadata.get("audio_files", [])
        if not audio_files:
            return None

        output_file.parent.mkdir(parents=True, exist_ok=True)
        total_segments = len(audio_files)

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)

            # Pre-render one reusable silence clip if any inter-segment gap is needed.
            silence_file: Optional[Path] = None
            if silence_duration_ms > 0 and total_segments > 1:
                silence_file = tmp_dir / "silence.mp3"
                _generate_silence_file(ffmpeg_path, silence_duration_ms, silence_file)

            # Build the concat list in metadata order, mirroring the original pydub loop:
            # silence is inserted after segment i whenever i is not the last index in the
            # *full* metadata list (i.e. based on position in audio_files, not on how many
            # segments actually existed on disk). This is deliberately left as-is: an
            # entry's position in audio_files -- not the count of entries actually
            # included below -- decides where silence goes, even now that audio_files
            # includes failed segments too.
            #
            # A failed segment (success is False) never has a file on disk, so it's
            # skipped below regardless; the explicit success check just makes that
            # intent legible instead of relying solely on the exists() check. Old
            # metadata files predate the "success" key -- treat it as True when absent,
            # matching every other reader of this field.
            concat_list_file = tmp_dir / "concat_list.txt"
            included_any = False
            with open(concat_list_file, 'w', encoding='utf-8') as f:
                for i, item in enumerate(audio_files, 1):
                    if not item.get("success", True):
                        continue
                    file_path = Path(item["file"])
                    if not file_path.exists():
                        logger.warning("Skipping missing audio segment: %s", file_path)
                        continue
                    f.write(_concat_list_entry(file_path) + "\n")
                    included_any = True
                    if silence_file is not None and i < total_segments:
                        f.write(_concat_list_entry(silence_file) + "\n")

            if not included_any:
                logger.error("No audio segment files exist on disk; nothing to merge")
                return None

            cmd = [
                ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list_file),
                "-c:a", "libmp3lame", "-q:a", "2",
                str(output_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            if result.returncode != 0:
                logger.error("ffmpeg merge failed (exit %d): %s", result.returncode, result.stderr)
                return None

        return output_file

    def regenerate_segment(
        self,
        metadata_file: Path,
        segment_index: int,
        text: Optional[str] = None,
        voice: Optional[str] = None,
        style_prompt: Optional[str] = None
    ) -> Dict:
        """
        Regenerate exactly one segment (by its 1-based `metadata.json` index),
        overwriting its audio file on disk and updating its metadata entry in place.

        Does not re-merge -- callers are expected to run merge_audio_files() against
        the same metadata_file afterwards so merged_audio.mp3 picks up the change.

        Args:
            metadata_file: Path to the task's existing metadata.json
            segment_index: 1-based index of the segment to regenerate, matching an
                existing entry's "index" field
            text: Optional replacement text; reuses the existing segment text when omitted
            voice: Optional replacement voice; reuses the existing segment voice when omitted
            style_prompt: Optional one-off TTS prompt for this regeneration only; falls
                back to DEFAULT_TTS_PROMPT when omitted (per-segment style is not
                persisted from the original generation, so there's nothing else to fall
                back to)

        Returns:
            Dictionary with the recomputed total_segments/success/failed counts and
            whether this specific regeneration succeeded

        Raises:
            ValueError: if segment_index has no matching entry in metadata
        """
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        audio_files = metadata.get("audio_files", [])
        entry = next((item for item in audio_files if item.get("index") == segment_index), None)
        if entry is None:
            raise ValueError(f"Segment index {segment_index} not found in metadata")

        text_to_use = text if text is not None else entry.get("text", "")
        voice_to_use = voice if voice is not None else entry.get("voice", "Kore")
        prompt_to_use = style_prompt if style_prompt is not None else DEFAULT_TTS_PROMPT
        speaker = entry.get("speaker", "Speaker 1")

        output_file = (
            Path(entry["file"]) if entry.get("file")
            else metadata_file.parent / f"{speaker.replace(' ', '_')}_{segment_index:03d}.{AUDIO_FORMAT}"
        )

        result = generate_single_audio(text_to_use, voice_to_use, output_file, prompt=prompt_to_use)

        # Update this entry in place, reflecting the latest attempt regardless of outcome
        # (mirroring how a fresh generation records text/voice for failed segments too).
        entry["text"] = text_to_use
        entry["voice"] = voice_to_use
        entry["file"] = str(output_file)
        entry["success"] = result["success"]
        entry["error"] = None if result["success"] else result.get("error")

        if not result["success"]:
            logger.error("Failed to regenerate audio for segment %d: %s", segment_index, entry["error"])

        fail_count = sum(1 for item in audio_files if not item.get("success", True))
        success_count = len(audio_files) - fail_count
        total_segments = metadata.get("total_segments", len(audio_files))

        metadata["success"] = success_count
        metadata["failed"] = fail_count
        metadata["audio_files"] = audio_files

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {
            "total_segments": total_segments,
            "success": success_count,
            "failed": fail_count,
            "regenerated_success": result["success"],
            "regenerated_error": entry["error"]
        }


# Singleton instance
_audio_service: Optional[AudioService] = None


def get_audio_service() -> AudioService:
    """Get or create audio service instance"""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
