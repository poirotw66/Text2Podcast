"""
File handling utilities
"""
import ast
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


def _validate_transcript(transcript) -> List[Tuple[str, str]]:
    """
    Validate that a parsed object is a list of 2-element (speaker, text) string pairs.
    Raises ValueError with a clear message otherwise. Tuples are normalized from
    whatever sequence type the source format produced (JSON has no tuple type, so
    JSON-sourced items arrive as 2-element lists).
    """
    if not isinstance(transcript, list):
        raise ValueError(f"Transcript must be a list, got {type(transcript).__name__}")

    normalized: List[Tuple[str, str]] = []
    for i, item in enumerate(transcript):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"Transcript item {i} must be a 2-element (speaker, text) pair, got {item!r}")
        speaker, text = item
        if not isinstance(speaker, str) or not isinstance(text, str):
            raise ValueError(f"Transcript item {i} must contain (str, str), got {item!r}")
        normalized.append((speaker, text))
    return normalized


def save_transcript(transcript: List[Tuple[str, str]], file_path: Path) -> Path:
    """
    Save transcript as JSON: a list of {"speaker": ..., "text": ...} objects.

    This replaced the old Python repr(list-of-tuples) format, which required an
    eval()/literal_eval() to read back and was an RCE risk when eval() was used.
    """
    ensure_directory(file_path.parent)
    payload = [{"speaker": speaker, "text": text} for speaker, text in transcript]
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    return file_path


def load_transcript(file_path: Path) -> List[Tuple[str, str]]:
    """
    Load transcript from file.

    Reads the current JSON format first. Falls back to ast.literal_eval (never
    eval()) to stay compatible with transcript files written by older versions
    of this app, which stored `str(list_of_tuples)` (a Python repr). The parsed
    result is always validated to be a list of 2-element string pairs.
    """
    content = load_text_file(file_path).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(content)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"Unable to parse transcript file {file_path}: not valid JSON or a Python literal ({e})")
    else:
        # New JSON format: list of {"speaker": ..., "text": ...} objects.
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            data = [(item.get("speaker"), item.get("text")) for item in data]

    return _validate_transcript(data)


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

