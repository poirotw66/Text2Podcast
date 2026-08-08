#!/usr/bin/env python3
"""
Audio file merging script
Read audio file list from metadata.json and merge them
"""

import json
from pathlib import Path

try:
    from pydub import AudioSegment
except ImportError:
    print("Error: pydub is required")
    print("Install command: pip install pydub")
    exit(1)


def merge_audio_files(
    metadata_file: str = "output/metadata.json",
    output_file: str = "output/merged_audio.mp3",
    silence_duration_ms: int = 500
):
    """
    Merge all audio files
    
    Args:
        metadata_file: Path to metadata file
        output_file: Output file path
        silence_duration_ms: Silence duration between audio segments (milliseconds)
    """
    # Read metadata
    metadata_path = Path(metadata_file)
    if not metadata_path.exists():
        print(f"Error: Metadata file not found: {metadata_file}")
        return
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    audio_files = metadata.get("audio_files", [])
    
    if not audio_files:
        print("Error: No audio files found in metadata")
        return
    
    print(f"Preparing to merge {len(audio_files)} audio files...")
    print()
    
    combined = AudioSegment.empty()
    
    for i, item in enumerate(audio_files, 1):
        file_path = Path(item["file"])
        
        if not file_path.exists():
            print(f"Warning: File does not exist, skipping: {file_path.name}")
            continue
        
        print(f"[{i}/{len(audio_files)}] Adding: {file_path.name} ({item['speaker']})")
        
        try:
            audio = AudioSegment.from_mp3(str(file_path))
            combined += audio
            
            # Add silence (not after the last segment)
            if i < len(audio_files):
                combined += AudioSegment.silent(duration=silence_duration_ms)
        except Exception as e:
            print(f"  Error: Unable to process file {file_path.name}: {e}")
            continue
    
    # Save merged file
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    
    print()
    print("Saving merged audio file...")
    combined.export(str(output_path), format="mp3")
    
    # Calculate duration
    duration_seconds = len(combined) / 1000.0
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    
    print()
    print("=" * 50)
    print("Merge completed!")
    print(f"Output file: {output_path.absolute()}")
    print(f"Total duration: {minutes} minutes {seconds} seconds")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Merge audio files")
    parser.add_argument(
        "-m", "--metadata",
        type=str,
        default="output/metadata.json",
        help="Path to metadata file (default: output/metadata.json)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output/merged_audio.mp3",
        help="Output file path (default: output/merged_audio.mp3)"
    )
    parser.add_argument(
        "-s", "--silence",
        type=int,
        default=500,
        help="Silence duration between audio segments in milliseconds (default: 500)"
    )
    
    args = parser.parse_args()
    
    merge_audio_files(args.metadata, args.output, args.silence)



