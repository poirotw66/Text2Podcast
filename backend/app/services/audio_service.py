"""
Audio generation service using Gemini TTS
Integrates functionality from generate_audio_gemini.py
"""
import os
import json
import time
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from google.cloud import texttospeech
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Thread-local storage for client
_thread_local = threading.local()

# Configure voices
SPEAKER_VOICES = {
    "Speaker 1": "Kore",
    "Speaker 2": "Charon"
}

# TTS configuration
TTS_MODEL = "gemini-2.5-flash-tts"
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
    retry_delay: float = 1.0
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
                prompt="Say the following naturally"
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


class AudioService:
    """Service for generating audio from transcript"""
    
    def __init__(self):
        """Initialize audio service"""
        pass
    
    def generate_audio_from_transcript(
        self,
        transcript: List[Tuple[str, str]],
        output_dir: Path,
        max_workers: int = 5
    ) -> Dict:
        """
        Generate audio files from transcript
        
        Args:
            transcript: List of (speaker, text) tuples
            output_dir: Output directory
            max_workers: Number of parallel workers
            
        Returns:
            Dictionary with audio files info and metadata
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare tasks
        tasks = []
        for i, (speaker, text) in enumerate(transcript, 1):
            voice = SPEAKER_VOICES.get(speaker, "Kore")
            output_file = output_dir / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
            tasks.append({
                "index": i,
                "speaker": speaker,
                "text": text,
                "voice": voice,
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
                    task["output_file"]
                ): task for task in tasks
            }
            
            results = {}
            for future in as_completed(future_to_task):
                result = future.result()
                task = future_to_task[future]
                results[task["index"]] = result
        
        # Sort and process results
        for index in sorted(results.keys()):
            result = results[index]
            if result["success"]:
                audio_files.append({
                    "speaker": tasks[index - 1]["speaker"],
                    "index": index,
                    "file": result["file"],
                    "text": result["text"],
                    "voice": result["voice"]
                })
                success_count += 1
            else:
                fail_count += 1
        
        # Save metadata
        metadata_file = output_dir / "metadata.json"
        metadata = {
            "total_segments": len(transcript),
            "success": success_count,
            "failed": fail_count,
            "model_used": TTS_MODEL,
            "language_code": LANGUAGE_CODE,
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
        Merge all audio files into one
        
        Args:
            metadata_file: Path to metadata.json
            output_file: Output merged file path
            silence_duration_ms: Silence duration between segments
            
        Returns:
            Path to merged file or None if failed
        """
        try:
            from pydub import AudioSegment
        except ImportError:
            return None
        
        # Read metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        audio_files = metadata.get("audio_files", [])
        if not audio_files:
            return None
        
        combined = AudioSegment.empty()
        
        for i, item in enumerate(audio_files, 1):
            file_path = Path(item["file"])
            if file_path.exists():
                if file_path.suffix.lower() == ".mp3":
                    audio = AudioSegment.from_mp3(str(file_path))
                elif file_path.suffix.lower() == ".wav":
                    audio = AudioSegment.from_wav(str(file_path))
                else:
                    audio = AudioSegment.from_mp3(str(file_path))
                
                combined += audio
                
                if i < len(audio_files):
                    combined += AudioSegment.silent(duration=silence_duration_ms)
        
        # Save merged file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        combined.export(str(output_file), format="mp3")
        
        return output_file


# Singleton instance
_audio_service: Optional[AudioService] = None


def get_audio_service() -> AudioService:
    """Get or create audio service instance"""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service

