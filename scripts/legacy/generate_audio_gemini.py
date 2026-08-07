#!/usr/bin/env python3
"""
Generate audio files using Google Cloud Text-to-Speech API with Gemini 2.5 Flash TTS model
Generate audio for two-person dialogue from transcript files with emotion markers
Uses Gemini 2.5 Flash TTS model for natural speech synthesis with style control
"""

import os
import json
import time
from pathlib import Path
from google.cloud import texttospeech
from typing import List, Tuple, Dict, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Skip if python-dotenv is not installed

# Thread-local storage to create independent client for each thread
_thread_local = threading.local()
# Print lock to ensure output is not mixed up
_print_lock = threading.Lock()

# Configure different voices for different speakers
# Gemini TTS voice names (using prebuilt voices)
SPEAKER_VOICES = {
    "Speaker 1": "Kore",      # Female voice
    "Speaker 2": "Charon"     # Male voice
}

# TTS model configuration - Using Gemini 2.5 Flash TTS
TTS_MODEL = "gemini-2.5-flash-tts"  # Gemini 2.5 Flash TTS model
AUDIO_FORMAT = "mp3"    # Output format: mp3, LINEAR16, OGG_OPUS, etc.
LANGUAGE_CODE = "cmn-tw"  # Chinese (Taiwan), change to "en-US" for English

# Audio encoding mapping
AUDIO_ENCODING_MAP = {
    "mp3": texttospeech.AudioEncoding.MP3,
    "linear16": texttospeech.AudioEncoding.LINEAR16,
    "ogg_opus": texttospeech.AudioEncoding.OGG_OPUS,
    "alaw": texttospeech.AudioEncoding.ALAW,
    "mulaw": texttospeech.AudioEncoding.MULAW,
}

# Emotion to prompt mapping for Gemini TTS
# Gemini TTS uses natural language prompts to control style, tone, and emotion
EMOTION_PROMPTS = {
    "excited": "Speak in an excited and enthusiastic tone",
    "calm": "Speak in a calm and peaceful tone",
    "curious": "Speak in a curious and questioning tone",
    "friendly": "Speak in a friendly and warm tone",
    "serious": "Speak in a serious and professional tone",
    "playful": "Speak in a playful and lighthearted tone",
    "thoughtful": "Speak in a thoughtful and reflective tone, with pauses for reflection",
    "surprised": "Speak in a surprised and astonished tone",
    "intense": "Speak in an intense and emphatic tone",
    "reflective": "Speak in a reflective and contemplative tone",
    "concerned": "Speak in a concerned and worried tone",
    "sad": "Speak in a sad and melancholic tone",
    "happy": "Speak in a happy and cheerful tone",
    "angry": "Speak in an angry and frustrated tone",
    "whisper": "Speak in a quiet whisper, as quietly as possible",
    "loud": "Speak loudly and clearly, with emphasis",
}


def parse_transcript(file_path: str) -> List[Tuple[str, str, Union[str, None]]]:
    """
    Parse transcript file with emotion support

    Supports two formats:
    1. Old format: [("Speaker 1", "text"), ...]
    2. New format: [("Speaker 1", "text", "emotion"), ...]

    Args:
        file_path: Path to transcript file

    Returns:
        List of (speaker, text, emotion) tuples, emotion can be None
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    # Parse Python list format
    try:
        transcript = eval(content)

        # Normalize to (speaker, text, emotion) format
        normalized = []
        for item in transcript:
            if len(item) == 2:
                # Old format: (speaker, text)
                normalized.append((item[0], item[1], None))
            elif len(item) == 3:
                # New format: (speaker, text, emotion)
                normalized.append((item[0], item[1], item[2]))
            else:
                raise ValueError(f"Invalid transcript format: expected 2 or 3 elements, got {len(item)}")

        return normalized
    except Exception as e:
        raise ValueError(f"Unable to parse transcript file: {e}")


def create_emotion_prompt(emotion: str = None) -> str:
    """
    Create a style prompt for Gemini TTS based on emotion

    Args:
        emotion: Emotion marker (e.g., "excited", "calm", "serious")

    Returns:
        Style prompt string for Gemini TTS
    """
    if not emotion or emotion not in EMOTION_PROMPTS:
        return "Say the following naturally"
    
    return EMOTION_PROMPTS[emotion]


def get_client() -> texttospeech.TextToSpeechClient:
    """Get Google Cloud Text-to-Speech client (lazy initialization, thread-safe)"""
    # Create independent client instance for each thread
    if not hasattr(_thread_local, 'client'):
        # Check for credentials
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            # Try to get from environment or use default
            pass
        
        _thread_local.client = texttospeech.TextToSpeechClient()
    return _thread_local.client


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable
    
    Args:
        error: Exception object
        
    Returns:
        True if error is retryable, False otherwise
    """
    error_str = str(error).lower()
    
    # Retryable errors (network issues, rate limits, temporary failures)
    retryable_keywords = [
        "timeout",
        "connection",
        "rate limit",
        "quota",
        "temporary",
        "503",
        "500",
        "429",
        "502",
        "504"
    ]
    
    # Non-retryable errors (content filter, invalid input, etc.)
    non_retryable_keywords = [
        "sensitive",
        "harmful content",
        "invalid",
        "permission denied",
        "not found",
        "disabled",
        "400"
    ]
    
    # Check for non-retryable errors first
    for keyword in non_retryable_keywords:
        if keyword in error_str:
            return False
    
    # Check for retryable errors
    for keyword in retryable_keywords:
        if keyword in error_str:
            return True
    
    # Default: don't retry unknown errors
    return False


def generate_single_audio(
    text: str,
    voice: str,
    output_file: Path,
    model: str = TTS_MODEL,
    index: int = None,
    speaker: str = None,
    total: int = None,
    emotion: str = None,
    language_code: str = LANGUAGE_CODE,
    prompt: str = None,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Dict:
    """
    Generate a single audio file with emotion support using Gemini TTS

    Args:
        text: Text to convert
        voice: Voice name (e.g., "Kore", "Charon")
        output_file: Output file path
        model: TTS model (default: gemini-2.5-flash-tts)
        index: Current index (for progress display)
        speaker: Speaker (for progress display)
        total: Total count (for progress display)
        emotion: Emotion marker (optional)
        language_code: Language code (default: cmn-tw)
        prompt: Custom style prompt (optional, overrides emotion-based prompt)
        max_retries: Maximum number of retries for retryable errors (default: 3)
        retry_delay: Delay between retries in seconds (default: 1.0)

    Returns:
        Dictionary containing results, with all information on success, error information on failure
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Create style prompt from emotion
            style_prompt = prompt if prompt else create_emotion_prompt(emotion)

            with _print_lock:
                if index and total:
                    print(f"[{index}/{total}] {speaker}:")
                if attempt > 0:
                    print(f"  Retry attempt {attempt}/{max_retries}")
                print(f"  Generating audio: {output_file.name}")
                print(f"  Model: {model}")
                print(f"  Voice: {voice}")
                if emotion:
                    print(f"  Emotion: {emotion}")
                if style_prompt:
                    print(f"  Style prompt: {style_prompt}")
                display_text = text[:80] + "..." if len(text) > 80 else text
                print(f"  Text: {display_text}")

            client = get_client()

            # Create synthesis input with text and prompt
            synthesis_input = texttospeech.SynthesisInput(
                text=text,
                prompt=style_prompt
            )

            # Select the voice
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

            # Perform the text-to-speech request
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_selection,
                audio_config=audio_config
            )

            # Save audio file
            with open(output_file, "wb") as out:
                out.write(response.audio_content)

            with _print_lock:
                if attempt > 0:
                    print(f"  ✓ Completed after {attempt} retry(ies): {output_file.name}\n")
                else:
                    print(f"  ✓ Completed: {output_file.name}\n")

            return {
                "success": True,
                "speaker": speaker,
                "index": index,
                "file": str(output_file),
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "prompt": style_prompt,
                "model_used": model,
                "language_code": language_code,
                "retries": attempt
            }

        except Exception as e:
            last_error = e
            error_str = str(e)
            
            # Check if error is retryable
            if attempt < max_retries and is_retryable_error(e):
                with _print_lock:
                    if index and total:
                        print(f"[{index}/{total}] {speaker}:")
                    print(f"  ⚠ Retryable error (attempt {attempt + 1}/{max_retries + 1}): {error_str}")
                    print(f"  Waiting {retry_delay} seconds before retry...\n")
                
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                # Non-retryable error or max retries reached
                with _print_lock:
                    if index and total:
                        print(f"[{index}/{total}] {speaker}:")
                    if attempt >= max_retries:
                        print(f"  ✗ Error after {max_retries} retries: {error_str}\n")
                    else:
                        print(f"  ✗ Error (non-retryable): {error_str}\n")
                
                return {
                    "success": False,
                    "speaker": speaker,
                    "index": index,
                    "error": error_str,
                    "emotion": emotion,
                    "retries": attempt,
                    "retryable": is_retryable_error(e) if attempt < max_retries else False
                }
    
    # Should not reach here, but just in case
    return {
        "success": False,
        "speaker": speaker,
        "index": index,
        "error": str(last_error) if last_error else "Unknown error",
        "emotion": emotion,
        "retries": max_retries
    }


def regenerate_failed_segments(
    metadata_file: str,
    output_dir: str = "output",
    model: str = TTS_MODEL,
    language_code: str = LANGUAGE_CODE,
    max_retries: int = 3,
    max_workers: int = 5
) -> Dict:
    """
    Regenerate failed audio segments from metadata file
    
    Args:
        metadata_file: Path to metadata.json file
        output_dir: Output directory
        model: TTS model (default: gemini-2.5-flash-tts)
        language_code: Language code (default: cmn-tw)
        max_retries: Maximum number of retries per segment (default: 3)
        max_workers: Maximum number of threads (default: 5)
    
    Returns:
        Dictionary containing regeneration results
    """
    metadata_path = Path(metadata_file)
    if not metadata_path.exists():
        print(f"Error: Metadata file not found: {metadata_file}")
        return {"success": 0, "failed": 0, "audio_files": []}
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    audio_files = metadata.get("audio_files", [])
    
    # Find failed segments (files that don't exist)
    failed_segments = []
    for item in audio_files:
        file_path = Path(item["file"])
        if not file_path.exists():
            failed_segments.append(item)
    
    if not failed_segments:
        print("No failed segments found to regenerate.")
        return {"success": 0, "failed": 0, "audio_files": []}
    
    print(f"Found {len(failed_segments)} failed segments to regenerate\n")
    
    # Regenerate failed segments
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(
                generate_single_audio,
                item["text"],
                item["voice"],
                Path(item["file"]),
                model,
                item["index"],
                item["speaker"],
                len(failed_segments),
                item.get("emotion"),
                language_code,
                item.get("prompt"),
                max_retries
            ): item for item in failed_segments
        }
        
        for future in as_completed(future_to_task):
            result = future.result()
            results[result["index"]] = result
    
    # Update metadata with regenerated segments
    success_count = 0
    fail_count = 0
    
    for item in audio_files:
        index = item["index"]
        if index in results:
            result = results[index]
            if result["success"]:
                # Update existing entry
                item.update({
                    "file": result["file"],
                    "prompt": result.get("prompt", item.get("prompt", "")),
                    "model_used": result.get("model_used", model),
                    "language_code": result.get("language_code", language_code)
                })
                success_count += 1
            else:
                fail_count += 1
    
    # Save updated metadata
    metadata["success"] = len([f for f in audio_files if Path(f["file"]).exists()])
    metadata["failed"] = metadata["total_segments"] - metadata["success"]
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print("\nRegeneration completed!")
    print(f"Success: {success_count} files")
    print(f"Failed: {fail_count} files")
    
    return {
        "success": success_count,
        "failed": fail_count,
        "audio_files": audio_files
    }


def generate_audio_from_transcript(
    transcript_file: str,
    output_dir: str = "output",
    model: str = TTS_MODEL,
    max_workers: int = 5,
    language_code: str = LANGUAGE_CODE,
    max_retries: int = 3,
    auto_retry_failed: bool = False
) -> Dict:
    """
    Generate all audio from transcript file with emotion support using Gemini TTS (using multithreading)

    Args:
        transcript_file: Path to transcript file
        output_dir: Output directory
        model: TTS model (default: gemini-2.5-flash-tts)
        max_workers: Maximum number of threads (default: 5)
        language_code: Language code (default: cmn-tw)
        max_retries: Maximum number of retries per segment (default: 3)
        auto_retry_failed: Automatically retry failed segments after initial generation (default: False)

    Returns:
        Dictionary containing generation results
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Parse transcript file
    print(f"Parsing transcript file: {transcript_file}")
    transcript = parse_transcript(transcript_file)
    print(f"Found {len(transcript)} dialogue segments")

    # Count emotions
    emotion_count = sum(1 for _, _, emotion in transcript if emotion)
    if emotion_count > 0:
        print(f"Found {emotion_count} segments with emotion markers")

    print(f"Using model: {model}")
    print(f"Using language: {language_code}")
    print(f"Using {max_workers} threads for parallel processing\n")

    # Prepare task list
    tasks = []
    for i, (speaker, text, emotion) in enumerate(transcript, 1):
        voice = SPEAKER_VOICES.get(speaker, "Kore")  # Default to Kore if speaker not found
        output_file = output_path / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
        tasks.append({
            "index": i,
            "speaker": speaker,
            "text": text,
            "emotion": emotion,
            "voice": voice,
            "output_file": output_file,
            "model": model,
            "total": len(transcript),
            "language_code": language_code
        })

    # Use thread pool to generate audio in parallel
    audio_files = []
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                generate_single_audio,
                task["text"],
                task["voice"],
                task["output_file"],
                task["model"],
                task["index"],
                task["speaker"],
                task["total"],
                task["emotion"],
                task["language_code"],
                None,  # prompt
                max_retries
            ): task for task in tasks
        }

        # Collect results (in completion order)
        results = {}
        for future in as_completed(future_to_task):
            result = future.result()
            results[result["index"]] = result

    # Sort by index and process results
    for index in sorted(results.keys()):
        result = results[index]
        if result["success"]:
            audio_files.append({
                "speaker": result["speaker"],
                "index": result["index"],
                "file": result["file"],
                "text": result["text"],
                "voice": result["voice"],
                "emotion": result.get("emotion"),
                "prompt": result.get("prompt", ""),
                "model_used": result.get("model_used", model),
                "language_code": result.get("language_code", language_code)
            })
            success_count += 1
        else:
            fail_count += 1

    # Save metadata
    metadata_file = output_path / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_segments": len(transcript),
            "emotion_segments": emotion_count,
            "success": success_count,
            "failed": fail_count,
            "model_used": model,
            "language_code": language_code,
            "audio_files": audio_files
        }, f, ensure_ascii=False, indent=2)

    print("\nCompleted!")
    print(f"Success: {success_count} files")
    print(f"Failed: {fail_count} files")
    if emotion_count > 0:
        print(f"Emotion markers applied: {emotion_count} segments")
    print(f"Output directory: {output_path.absolute()}")
    print(f"Metadata: {metadata_file}")
    
    # Auto-retry failed segments if enabled
    if auto_retry_failed and fail_count > 0:
        print(f"\n{'=' * 60}")
        print("Auto-retrying failed segments...")
        print(f"{'=' * 60}\n")
        
        regenerate_failed_segments(
            str(metadata_file),
            output_dir,
            model,
            language_code,
            max_retries,
            max_workers
        )
        
        # Reload metadata to get updated counts
        with open(metadata_file, 'r', encoding='utf-8') as f:
            updated_metadata = json.load(f)
        
        # Update counts
        success_count = len([f for f in audio_files if Path(f["file"]).exists()])
        fail_count = updated_metadata["total_segments"] - success_count
        
        print("\nFinal results after retry:")
        print(f"Success: {success_count} files")
        print(f"Failed: {fail_count} files")

    return {
        "success": success_count,
        "failed": fail_count,
        "audio_files": audio_files,
        "output_dir": str(output_path)
    }


def merge_audio_files(
    metadata_file: str,
    output_file: str = "output/merged_audio.mp3",
    silence_duration_ms: int = 500
) -> str:
    """
    Merge all audio files (requires pydub installation)

    Args:
        metadata_file: Path to metadata file
        output_file: Output file path
        silence_duration_ms: Silence duration between audio segments (milliseconds)

    Returns:
        Path to merged file
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("Error: pydub is required to merge audio")
        print("Install command: pip install pydub")
        return None

    # Read metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    audio_files = metadata.get("audio_files", [])

    if not audio_files:
        print("No audio files found")
        return None

    print(f"Merging {len(audio_files)} audio files...")

    combined = AudioSegment.empty()

    for i, item in enumerate(audio_files, 1):
        file_path = item["file"]
        emotion = item.get("emotion", "N/A")
        model_used = item.get("model_used", "N/A")
        print(f"  [{i}/{len(audio_files)}] Adding: {Path(file_path).name} (emotion: {emotion}, model: {model_used})")

        # Load audio file (handle different formats)
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".mp3":
            audio = AudioSegment.from_mp3(file_path)
        elif file_ext == ".wav":
            audio = AudioSegment.from_wav(file_path)
        elif file_ext == ".ogg":
            audio = AudioSegment.from_ogg(file_path)
        else:
            # Try to load as MP3 by default
            audio = AudioSegment.from_mp3(file_path)
        
        combined += audio

        # Add silence (not after the last segment)
        if i < len(audio_files):
            combined += AudioSegment.silent(duration=silence_duration_ms)

    # Save merged file
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    combined.export(str(output_path), format="mp3")

    print(f"\nMerge completed: {output_path.absolute()}")
    return str(output_path)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate audio using Google Cloud Text-to-Speech API with Gemini 2.5 Flash TTS model and emotion support"
    )
    parser.add_argument(
        "transcript_file",
        type=str,
        nargs='?',
        help="Path to transcript file (supports format: [(\"Speaker\", \"text\", \"emotion\"), ...])"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output",
        help="Output directory (default: output)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=TTS_MODEL,
        help=f"TTS model (default: {TTS_MODEL})"
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default=LANGUAGE_CODE,
        help=f"Language code (default: {LANGUAGE_CODE}, e.g., cmn-tw, en-US)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Automatically merge all audio files after generation (requires pydub)"
    )
    parser.add_argument(
        "--merge-output",
        type=str,
        default=None,
        help="Output file path for merged audio (default: output/merged_audio.mp3)"
    )
    parser.add_argument(
        "-j", "--workers",
        type=int,
        default=5,
        help="Number of threads for parallel processing (default: 5)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retries for retryable errors (default: 3)"
    )
    parser.add_argument(
        "--auto-retry",
        action="store_true",
        help="Automatically retry failed segments after initial generation"
    )
    parser.add_argument(
        "--retry-failed",
        type=str,
        default=None,
        help="Regenerate failed segments from metadata file (path to metadata.json)"
    )
    parser.add_argument(
        "--list-emotions",
        action="store_true",
        help="List all supported emotion markers and exit"
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available Gemini TTS voices and exit"
    )

    args = parser.parse_args()

    # List emotions and exit
    if args.list_emotions:
        print("Supported emotion markers:")
        print("(These emotions are expressed through natural language style prompts)")
        print()
        for emotion, prompt in sorted(EMOTION_PROMPTS.items()):
            print(f"  {emotion:15s} -> {prompt}")
        return

    # List voices and exit
    if args.list_voices:
        print("Available Gemini TTS voices:")
        print("(Note: Voice availability may vary by language)")
        print()
        print("Female voices: Achernar, Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux, Kore, Laomedeia, Leda, Pulcherrima, Sulafat, Vindemiatrix, Zephyr")
        print("Male voices: Achird, Algenib, Algieba, Alnilam, Charon, Enceladus, Fenrir, Iapetus, Orus, Puck, Rasalgethi, Sadachbia, Sadaltager, Schedar, Umbriel, Zubenelgenubi")
        print()
        print("Currently configured:")
        for speaker, voice in SPEAKER_VOICES.items():
            print(f"  {speaker}: {voice}")
        return

    # Handle retry-failed mode
    if args.retry_failed:
        if not Path(args.retry_failed).exists():
            print(f"Error: Metadata file does not exist: {args.retry_failed}")
            return
        
        output_dir = Path(args.retry_failed).parent
        regenerate_failed_segments(
            args.retry_failed,
            str(output_dir),
            args.model,
            args.language,
            args.max_retries,
            args.workers
        )
        
        # Merge if needed
        if args.merge:
            merge_output = args.merge_output or str(output_dir / "merged_audio.mp3")
            merge_audio_files(args.retry_failed, merge_output)
        
        return
    
    # Check if transcript_file is provided
    if not args.transcript_file:
        parser.error("transcript_file is required (unless using --list-emotions, --list-voices, or --retry-failed)")

    # Check Google Cloud credentials
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("Warning: GOOGLE_CLOUD_PROJECT environment variable is not set")
        print("The client will use default credentials if available")
        print("Make sure you have set up Google Cloud authentication:")
        print("  Method 1: Set GOOGLE_APPLICATION_CREDENTIALS to your service account key file")
        print("  Method 2: Use 'gcloud auth application-default login'")
        print("  Method 3: Set GOOGLE_CLOUD_PROJECT environment variable")

    # Check if file exists
    if not Path(args.transcript_file).exists():
        print(f"Error: File does not exist: {args.transcript_file}")
        return

    # Generate audio
    result = generate_audio_from_transcript(
        args.transcript_file,
        args.output,
        args.model,
        args.workers,
        args.language,
        args.max_retries,
        args.auto_retry
    )

    # Merge if needed
    if args.merge:
        metadata_file = Path(args.output) / "metadata.json"
        merge_output = args.merge_output or str(Path(args.output) / "merged_audio.mp3")
        merge_audio_files(str(metadata_file), merge_output)


if __name__ == "__main__":
    main()

