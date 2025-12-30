"""
File handling utilities
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, create if not"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_text_file(content: str, file_path: Path) -> Path:
    """Save text content to file"""
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return file_path


def load_text_file(file_path: Path) -> str:
    """Load text content from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def save_transcript(transcript: List[Tuple[str, str]], file_path: Path) -> Path:
    """Save transcript as Python list format"""
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(transcript))
    return file_path


def load_transcript(file_path: Path) -> List[Tuple[str, str]]:
    """Load transcript from file"""
    content = load_text_file(file_path).strip()
    try:
        transcript = eval(content)
        return transcript
    except Exception as e:
        raise ValueError(f"Unable to parse transcript file: {e}")


def save_metadata(metadata: Dict, file_path: Path) -> Path:
    """Save metadata as JSON"""
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return file_path


def load_metadata(file_path: Path) -> Dict:
    """Load metadata from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

