#!/usr/bin/env python3
"""
Regenerate failed audio segments and merge all audio files
"""

import sys
from pathlib import Path
import json

# Import from generate_audio_gemini
from generate_audio_gemini import (
    generate_single_audio,
    SPEAKER_VOICES,
    TTS_MODEL,
    LANGUAGE_CODE,
    merge_audio_files
)

# Failed segments: index 2, 3, 6
failed_segments = [
    (2, 'Speaker 2', '等一下，我想先確認一件事。你是說這一整段，包括妓院、重傷、假死、師父追殺，真正的核心其實都不是江湖恩怨，而是情？'),
    (3, 'Speaker 1', '沒錯，而且不是安全、溫柔、被祝福的情，而是那種會讓人想自我毀滅、會讓人破戒、會讓人不顧一切的情。我們先從儀琳開始，因為她在這一回裡，整個人其實已經是碎掉的狀態。'),
    (6, 'Speaker 2', '這其實跟現實生活很像。很多人在重大創傷之後，會一直回到那種如果當初怎樣就好了的迴圈。')
]

def regenerate_failed_segments():
    """Regenerate failed audio segments"""
    output_path = Path('output')
    print('Regenerating failed segments...\n')

    results = []
    for index, speaker, text in failed_segments:
        voice = SPEAKER_VOICES.get(speaker, 'Kore')
        output_file = output_path / f'{speaker.replace(" ", "_")}_{index:03d}.mp3'
        
        result = generate_single_audio(
            text=text,
            voice=voice,
            output_file=output_file,
            model=TTS_MODEL,
            index=index,
            speaker=speaker,
            total=len(failed_segments),
            emotion=None,
            language_code=LANGUAGE_CODE
        )
        
        results.append(result)
        
        if result['success']:
            print(f'✓ Successfully regenerated index {index}\n')
        else:
            print(f'✗ Failed to regenerate index {index}: {result.get("error", "Unknown error")}\n')
    
    return results

def update_metadata():
    """Update metadata.json with regenerated segments"""
    metadata_file = Path('output/metadata.json')
    
    if not metadata_file.exists():
        print(f"Error: {metadata_file} not found")
        return
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Read the transcript to get all segments
    transcript_file = Path('example/pound2.txt')
    if not transcript_file.exists():
        print(f"Error: {transcript_file} not found")
        return
    
    # Parse transcript
    with open(transcript_file, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    transcript = eval(content)
    
    # Rebuild audio_files list with all segments
    audio_files = []
    existing_files = {item['index']: item for item in metadata.get('audio_files', [])}
    
    for i, (speaker, text) in enumerate(transcript, 1):
        if i in existing_files:
            # Use existing entry
            audio_files.append(existing_files[i])
        else:
            # Check if file exists
            output_file = Path('output') / f'{speaker.replace(" ", "_")}_{i:03d}.mp3'
            if output_file.exists():
                # Create entry for newly generated file
                voice = SPEAKER_VOICES.get(speaker, 'Kore')
                audio_files.append({
                    "speaker": speaker,
                    "index": i,
                    "file": str(output_file),
                    "text": text,
                    "voice": voice,
                    "emotion": None,
                    "prompt": "Say the following naturally",
                    "model_used": TTS_MODEL,
                    "language_code": LANGUAGE_CODE
                })
    
    # Sort by index
    audio_files.sort(key=lambda x: x['index'])
    
    # Update metadata
    metadata['audio_files'] = audio_files
    metadata['success'] = len([f for f in audio_files if Path(f['file']).exists()])
    metadata['failed'] = metadata['total_segments'] - metadata['success']
    
    # Save updated metadata
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"\nUpdated metadata.json")
    print(f"Total segments: {metadata['total_segments']}")
    print(f"Success: {metadata['success']}")
    print(f"Failed: {metadata['failed']}")

def main():
    """Main function"""
    print("=" * 60)
    print("Regenerating Failed Segments")
    print("=" * 60)
    print()
    
    # Step 1: Regenerate failed segments
    results = regenerate_failed_segments()
    
    # Check if all regenerations were successful
    all_success = all(r['success'] for r in results)
    
    if not all_success:
        print("Warning: Some segments failed to regenerate")
        for r in results:
            if not r['success']:
                print(f"  Index {r['index']}: {r.get('error', 'Unknown error')}")
        print()
    
    # Step 2: Update metadata
    print("Updating metadata...")
    update_metadata()
    print()
    
    # Step 3: Merge all audio files
    print("=" * 60)
    print("Merging All Audio Files")
    print("=" * 60)
    print()
    
    metadata_file = Path('output/metadata.json')
    merge_output = Path('output/merged_audio.mp3')
    
    result = merge_audio_files(
        str(metadata_file),
        str(merge_output),
        silence_duration_ms=500
    )
    
    if result:
        print(f"\n✓ All done! Merged audio saved to: {result}")
    else:
        print("\n✗ Failed to merge audio files")

if __name__ == "__main__":
    main()

