#!/usr/bin/env python3
"""
Generate audio files using OpenAI TTS API with emotion support
Generate audio for two-person dialogue from transcript files with emotion markers
"""

import os
import json
from pathlib import Path
from openai import OpenAI
from typing import List, Tuple, Dict, Union
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

# Emotion to natural text enhancement mapping
# Use natural interjections and punctuation to guide TTS voice tone
# These are embedded naturally in the text, not as instructions
EMOTION_ENHANCEMENTS = {
    "excited": {
        "prefix": "哇，",  # Natural interjection for excitement
        "suffix": "！",
        "punctuation_replace": True  # Replace 。 with ！
    },
    "calm": {
        "prefix": "",
        "suffix": "。",
        "punctuation_replace": False
    },
    "curious": {
        "prefix": "嗯……",  # Natural hesitation for curiosity
        "suffix": "？",
        "punctuation_replace": True  # Replace 。 with ？
    },
    "friendly": {
        "prefix": "",
        "suffix": "。",
        "punctuation_replace": False
    },
    "serious": {
        "prefix": "",
        "suffix": "。",
        "punctuation_replace": False
    },
    "playful": {
        "prefix": "哈哈，",  # Natural laughter for playfulness
        "suffix": "。",
        "punctuation_replace": False
    },
    "thoughtful": {
        "prefix": "嗯……",  # Long pause for thought
        "suffix": "……",
        "punctuation_replace": True  # Replace 。 with ……
    },
    "surprised": {
        "prefix": "什麼？",  # Natural surprise expression
        "suffix": "！",
        "punctuation_replace": True
    },
    "intense": {
        "prefix": "",
        "suffix": "——",  # Dash for intensity
        "punctuation_replace": True
    },
    "reflective": {
        "prefix": "",
        "suffix": "……",  # Long pause for reflection
        "punctuation_replace": True
    },
    "concerned": {
        "prefix": "唉，",  # Natural concern expression
        "suffix": "……",
        "punctuation_replace": False
    },
    "sad": {
        "prefix": "唉，",  # Natural sadness expression
        "suffix": "……",
        "punctuation_replace": False
    },
    "happy": {
        "prefix": "",
        "suffix": "！",
        "punctuation_replace": True
    },
    "angry": {
        "prefix": "",
        "suffix": "！",
        "punctuation_replace": True
    },
    "whisper": {
        "prefix": "",
        "suffix": "。",
        "punctuation_replace": False
    },
    "loud": {
        "prefix": "",
        "suffix": "！",
        "punctuation_replace": True
    },
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


def enhance_text_with_emotion(text: str, emotion: str = None) -> str:
    """
    Enhance text with natural emotion expressions to guide TTS voice tone
    Uses natural interjections and punctuation instead of instruction-like prompts
    
    Args:
        text: Original text
        emotion: Emotion marker (e.g., "excited", "calm", "serious")
        
    Returns:
        Enhanced text with natural emotion expressions
    """
    if not emotion or emotion not in EMOTION_ENHANCEMENTS:
        return text
    
    enhancement = EMOTION_ENHANCEMENTS[emotion]
    enhanced = text.strip()
    
    # Add prefix (natural interjections)
    if enhancement["prefix"]:
        # Only add if text doesn't already start with similar expressions
        prefix_chars = ("哇", "嗯", "什麼", "唉", "哈哈", "啊", "哦")
        if not any(enhanced.startswith(char) for char in prefix_chars):
            enhanced = enhancement["prefix"] + enhanced
    
    # Handle punctuation replacement
    if enhancement["punctuation_replace"]:
        # Remove trailing punctuation first (preserve spaces)
        original_end = enhanced
        enhanced = enhanced.rstrip("。！？……——")
        # Only add new suffix if we actually removed punctuation or text doesn't end with target suffix
        if original_end != enhanced or not enhanced.endswith(enhancement["suffix"]):
            enhanced = enhanced + enhancement["suffix"]
    else:
        # Just ensure proper punctuation
        if not enhanced.rstrip().endswith(('。', '！', '？', '……', '——')):
            enhanced = enhanced.rstrip() + enhancement["suffix"]
    
    return enhanced


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
    total: int = None,
    emotion: str = None
) -> Dict:
    """
    Generate a single audio file with emotion support
    
    Args:
        text: Text to convert
        voice: Voice type
        output_file: Output file path
        model: TTS model
        index: Current index (for progress display)
        speaker: Speaker (for progress display)
        total: Total count (for progress display)
        emotion: Emotion marker (optional)
        
    Returns:
        Dictionary containing results, with all information on success, error information on failure
    """
    try:
        # Enhance text with emotion prompts
        enhanced_text = enhance_text_with_emotion(text, emotion)
        
        with _print_lock:
            if index and total:
                print(f"[{index}/{total}] {speaker}:")
            print(f"  Generating audio: {output_file.name}")
            if emotion:
                print(f"  Emotion: {emotion}")
            if enhanced_text:
                display_text = enhanced_text[:80] + "..." if len(enhanced_text) > 80 else enhanced_text
                print(f"  Text: {display_text}")
        
        openai_client = get_client()
        response = openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=enhanced_text,
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
            "enhanced_text": enhanced_text,
            "voice": voice,
            "emotion": emotion
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
            "error": str(e),
            "emotion": emotion
        }


def generate_audio_from_transcript(
    transcript_file: str,
    output_dir: str = "output",
    model: str = TTS_MODEL,
    max_workers: int = 5
) -> Dict:
    """
    Generate all audio from transcript file with emotion support (using multithreading)
    
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
    
    # Count emotions
    emotion_count = sum(1 for _, _, emotion in transcript if emotion)
    if emotion_count > 0:
        print(f"Found {emotion_count} segments with emotion markers")
    
    print(f"Using {max_workers} threads for parallel processing\n")
    
    # Prepare task list
    tasks = []
    for i, (speaker, text, emotion) in enumerate(transcript, 1):
        voice = SPEAKER_VOICES.get(speaker, "alloy")
        output_file = output_path / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
        tasks.append({
            "index": i,
            "speaker": speaker,
            "text": text,
            "emotion": emotion,
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
                task["total"],
                task["emotion"]
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
                "enhanced_text": result.get("enhanced_text", result["text"]),
                "voice": result["voice"],
                "emotion": result.get("emotion")
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
            "audio_files": audio_files
        }, f, ensure_ascii=False, indent=2)
    
    print("\nCompleted!")
    print(f"Success: {success_count} files")
    print(f"Failed: {fail_count} files")
    if emotion_count > 0:
        print(f"Emotion markers applied: {emotion_count} segments")
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
        emotion = item.get("emotion", "N/A")
        print(f"  [{i}/{len(audio_files)}] Adding: {Path(file_path).name} (emotion: {emotion})")
        
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
        description="Generate audio using OpenAI TTS API with emotion support"
    )
    parser.add_argument(
        "transcript_file",
        type=str,
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
    parser.add_argument(
        "--list-emotions",
        action="store_true",
        help="List all supported emotion markers and exit"
    )
    
    args = parser.parse_args()
    
    # List emotions and exit
    if args.list_emotions:
        print("Supported emotion markers:")
        print("(These emotions are expressed naturally through interjections and punctuation)")
        print()
        for emotion, enhancement in sorted(EMOTION_ENHANCEMENTS.items()):
            prefix = enhancement["prefix"] if enhancement["prefix"] else "(none)"
            suffix = enhancement["suffix"]
            print(f"  {emotion:15s} -> prefix: '{prefix}', suffix: '{suffix}'")
        return
    
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

