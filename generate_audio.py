#!/usr/bin/env python3
"""
Generate audio files using OpenAI TTS API
Generate audio for two-person dialogue from transcript files
"""

import os
import json
from pathlib import Path
from openai import OpenAI
from typing import List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Skip if python-dotenv is not installed

# Initialize OpenAI client (lazy initialization, checked in main function)
client = None
# Thread-local storage to create independent client for each thread
_thread_local = threading.local()
# Print lock to ensure output is not mixed up
_print_lock = threading.Lock()

# Configure different voices for different speakers
SPEAKER_VOICES = {
    "Speaker 1": "nova",      # More professional and clear voice
    "Speaker 2": "shimmer"    # More lively and energetic voice
}

# TTS model configuration
TTS_MODEL = "tts-1"  # Use high-quality model, change to "tts-1" to save costs if needed
AUDIO_FORMAT = "mp3"    # Output format: mp3, opus, aac, flac


def parse_transcript(file_path: str) -> List[Tuple[str, str]]:
    """
    Parse transcript file
    
    Args:
        file_path: Path to transcript file
        
    Returns:
        List of (speaker, text) tuples
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # Parse Python list format
    # Format: [("Speaker 1", "text"), ...]
    try:
        transcript = eval(content)
        return transcript
    except Exception as e:
        raise ValueError(f"Unable to parse transcript file: {e}")


def get_client() -> OpenAI:
    """Get OpenAI client (lazy initialization, thread-safe)"""
    # Create independent client instance for each thread
    if not hasattr(_thread_local, 'client'):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set, please check .env file or environment variables")
        _thread_local.client = OpenAI(api_key=api_key)
    return _thread_local.client


def generate_single_audio(
    text: str,
    voice: str,
    output_file: Path,
    model: str = TTS_MODEL,
    index: int = None,
    speaker: str = None,
    total: int = None
) -> Dict:
    """
    Generate a single audio file
    
    Args:
        text: Text to convert
        voice: Voice type
        output_file: Output file path
        model: TTS model
        index: Current index (for progress display)
        speaker: Speaker (for progress display)
        total: Total count (for progress display)
        
    Returns:
        Dictionary containing results, with all information on success, error information on failure
    """
    try:
        with _print_lock:
            if index and total:
                print(f"[{index}/{total}] {speaker}:")
            print(f"  Generating audio: {output_file.name}")
            if text:
                print(f"  Text: {text[:50]}..." if len(text) > 50 else f"  Text: {text}")
        
        openai_client = get_client()
        response = openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format=AUDIO_FORMAT
        )
        
        # Save audio file
        response.stream_to_file(str(output_file))
        
        with _print_lock:
            print(f"  ✓ Completed: {output_file.name}\n")
        
        return {
            "success": True,
            "speaker": speaker,
            "index": index,
            "file": str(output_file),
            "text": text,
            "voice": voice
        }
        
    except Exception as e:
        with _print_lock:
            if index and total:
                print(f"[{index}/{total}] {speaker}:")
            print(f"  ✗ Error: {e}\n")
        return {
            "success": False,
            "speaker": speaker,
            "index": index,
            "error": str(e)
        }


def generate_audio_from_transcript(
    transcript_file: str,
    output_dir: str = "output",
    model: str = TTS_MODEL,
    max_workers: int = 5
) -> Dict:
    """
    Generate all audio from transcript file (using multithreading)
    
    Args:
        transcript_file: Path to transcript file
        output_dir: Output directory
        model: TTS model
        max_workers: Maximum number of threads (default: 5)
        
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
    print(f"Using {max_workers} threads for parallel processing\n")
    
    # Prepare task list
    tasks = []
    for i, (speaker, text) in enumerate(transcript, 1):
        voice = SPEAKER_VOICES.get(speaker, "alloy")
        output_file = output_path / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
        tasks.append({
            "index": i,
            "speaker": speaker,
            "text": text,
            "voice": voice,
            "output_file": output_file,
            "model": model,
            "total": len(transcript)
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
                task["total"]
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
                "voice": result["voice"]
            })
            success_count += 1
        else:
            fail_count += 1
    
    # Save metadata
    metadata_file = output_path / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_segments": len(transcript),
            "success": success_count,
            "failed": fail_count,
            "audio_files": audio_files
        }, f, ensure_ascii=False, indent=2)
    
    print("\nCompleted!")
    print(f"Success: {success_count} files")
    print(f"Failed: {fail_count} files")
    print(f"Output directory: {output_path.absolute()}")
    print(f"Metadata: {metadata_file}")
    
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
        print(f"  [{i}/{len(audio_files)}] Adding: {Path(file_path).name}")
        
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
    
    parser = argparse.ArgumentParser(description="Generate audio using OpenAI TTS API")
    parser.add_argument(
        "transcript_file",
        type=str,
        help="Path to transcript file"
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
        choices=["tts-1", "tts-1-hd"],
        help=f"TTS model (default: {TTS_MODEL})"
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
    
    args = parser.parse_args()
    
    # Check API Key (will be checked again in get_client(), here we check early to give friendly prompt)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: Please set OPENAI_API_KEY")
        print("Method 1: Set in .env file: OPENAI_API_KEY=your-api-key")
        print("Method 2: Set environment variable: export OPENAI_API_KEY='your-api-key'")
        return
    
    # Check if file exists
    if not Path(args.transcript_file).exists():
        print(f"Error: File does not exist: {args.transcript_file}")
        return
    
    # Generate audio
    result = generate_audio_from_transcript(
        args.transcript_file,
        args.output,
        args.model,
        args.workers
    )
    
    # Merge if needed
    if args.merge:
        metadata_file = Path(args.output) / "metadata.json"
        merge_output = args.merge_output or str(Path(args.output) / "merged_audio.mp3")
        merge_audio_files(str(metadata_file), merge_output)


if __name__ == "__main__":
    main()

