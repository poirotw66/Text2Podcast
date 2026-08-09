"""
Shared TTS pipeline logic, extracted so there is exactly one place that knows
the preflight rules, voice/style default-resolution rules, and
generate-then-merge orchestration for turning a transcript into a podcast MP3.

Why this module exists
-----------------------
There are three entry points onto `app.services.audio_service`:

  1. `app/api/routes.py` -- the HTTP API (async, TaskManager-backed)
  2. `.claude/skills/text2podcast/scripts/synthesize.py` -- the skill's CLI
  3. `app/mcp_server.py` -- the local stdio MCP server

The CLI already carried preflight checks, voice/style default-resolution, and
partial-failure summarising that the MCP server also needs. This module is
that logic, extracted so the CLI and the MCP server are both thin wrappers
over it instead of two more divergent copies of the same rules.

`routes.py` is deliberately NOT refactored onto this module -- it has its own
async/TaskManager concerns (background tasks, SSE progress, task eviction)
that make touching it unnecessary risk for this extraction. Its behavior is
unchanged.

Nothing here talks to argparse, sys.exit, or MCP types -- callers translate
these structures into a CLI exit code / stderr text or an MCP tool error /
structured result, respectively.
"""
import dataclasses
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.services.audio_service import (
    AudioService,
    DEFAULT_SPEAKER_VOICES,
    _require_ffmpeg,
    get_audio_service,
)

# Per section 3 of the HTTP API contract (see app/api/routes.py), style_settings
# values are capped at this many characters. Duplicated here (as a literal,
# matching value) rather than imported from routes.py, since routes.py is
# explicitly out of scope for this refactor and importing app.mcp_server-facing
# code from it (or vice versa) would create exactly the coupling this
# extraction is trying to avoid in the other direction.
MAX_STYLE_PROMPT_LENGTH = 200


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class PreflightProblem:
    """One failed prerequisite check, structured rather than printed/exited."""
    check: str      # short machine-friendly identifier, e.g. "ffmpeg"
    message: str    # human-readable description of what's wrong
    fix_hint: str    # what to do about it


def check_prerequisites() -> List[PreflightProblem]:
    """
    Check ffmpeg on PATH, google-cloud-texttospeech importable, and Google
    Cloud credentials resolvable. Returns a list of structured problems
    (empty if everything looks fine) instead of printing or exiting -- the
    CLI formats these for a terminal and exits non-zero; the MCP server turns
    them into a tool error.

    Note on reachability: this module (like the CLI and the MCP server that
    import it) already depends on `app.services.audio_service`, which itself
    imports `google.cloud.texttospeech` unconditionally at module level. In
    practice that means the "package not installed" problem below can only
    ever be observed by calling this function directly/programmatically (as
    the tests do) -- by the time any real caller could reach this function,
    the import already succeeded or the process already failed to start.
    It's kept here anyway per the extraction's brief (the CLI's own
    lighter-weight, import-time version of this same check is what actually
    protects the end-to-end path -- see `_load_backend_modules()` in
    synthesize.py) and because it *is* meaningful for anyone calling
    `check_prerequisites()` as a library function rather than going through
    one of the two real entry points.
    """
    problems: List[PreflightProblem] = []

    try:
        _require_ffmpeg()
    except RuntimeError as e:
        # _require_ffmpeg()'s own message is already the complete, actionable
        # fix (it names the exact install commands) -- no separate fix_hint
        # to add without just repeating it.
        problems.append(PreflightProblem(check="ffmpeg", message=str(e), fix_hint=""))

    try:
        import google.cloud.texttospeech  # noqa: F401
    except ImportError:
        problems.append(PreflightProblem(
            check="google-cloud-texttospeech",
            message="The `google-cloud-texttospeech` package is not installed.",
            fix_hint="pip install google-cloud-texttospeech==2.37.0 "
                      "(or `pip install -r backend/requirements.txt`).",
        ))
        # Credentials can't be meaningfully checked without the SDK present.
        return problems

    import os

    cred_path_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path_str:
        if not Path(cred_path_str).is_file():
            problems.append(PreflightProblem(
                check="credentials",
                message=f"GOOGLE_APPLICATION_CREDENTIALS is set to '{cred_path_str}', "
                        "but that file does not exist.",
                fix_hint="Point it at a valid Google Cloud service-account key JSON file, e.g.\n"
                         "    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json",
            ))
    else:
        try:
            import google.auth
            google.auth.default()
        except Exception as e:
            problems.append(PreflightProblem(
                check="credentials",
                message="No Google Cloud credentials found (GOOGLE_APPLICATION_CREDENTIALS is "
                        "not set, and no Application Default Credentials are available).",
                fix_hint=(
                    "Either\n"
                    "    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json\n"
                    "  or\n"
                    "    gcloud auth application-default login\n"
                    f"(underlying error: {e})"
                ),
            ))

    return problems


# ---------------------------------------------------------------------------
# Voice / style resolution
# ---------------------------------------------------------------------------
def resolve_voice_settings(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Seed with DEFAULT_SPEAKER_VOICES, then layer `overrides` on top.

    This exists because `AudioService.generate_audio_from_transcript` falls
    back an *unmapped* speaker in a partial voice_settings dict straight to a
    hardcoded "Kore" rather than DEFAULT_SPEAKER_VOICES -- so passing a
    partial override dict straight through would silently change more than
    the caller asked for. Seeding here keeps "unspecified speakers fall back
    to the module defaults" true for every caller, not just the ones that
    remember to do this themselves.
    """
    voice_settings = dict(DEFAULT_SPEAKER_VOICES)
    if overrides:
        voice_settings.update(overrides)
    return voice_settings


def resolve_style_settings(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Style settings have no baked-in per-speaker defaults to seed from --
    `AudioService.generate_audio_from_transcript` already falls unmapped
    speakers back to DEFAULT_TTS_PROMPT on its own, so unlike voice settings
    there's nothing to preserve beyond copying the caller's overrides.
    """
    return dict(overrides) if overrides else {}


def validate_style_settings(styles: Optional[Dict[str, str]], max_length: int = MAX_STYLE_PROMPT_LENGTH) -> None:
    """Raise ValueError naming the offending speaker if any style prompt exceeds `max_length`."""
    if not styles:
        return
    for speaker, style_prompt in styles.items():
        if len(style_prompt) > max_length:
            raise ValueError(f"style for {speaker!r} exceeds {max_length} characters")


# ---------------------------------------------------------------------------
# Working-files layout
# ---------------------------------------------------------------------------
def segments_dir_for(output_path: Path) -> Path:
    """
    The per-segment working-files directory for a synthesis run, deterministically
    derived from its `output_path` alone so a later `regenerate_segment` call --
    given only the same output_path -- can find it again without needing a
    separately-tracked job id.

    Lives alongside the merged output file (as a sibling directory) rather than
    under a tempdir, because unlike the CLI (a one-shot, fire-and-forget
    invocation that deletes its working directory once merged, by default) an
    MCP client may come back later in a separate tool call and ask to
    regenerate a single segment of an episode that already exists on disk.
    """
    return output_path.with_name(output_path.stem + ".segments")


def metadata_file_for(output_path: Path) -> Path:
    """The `metadata.json` a `synthesize_to_file()` run for `output_path` wrote."""
    return segments_dir_for(output_path) / "metadata.json"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
class PipelineError(Exception):
    """Base class for synthesize_to_file() failures."""


class AllSegmentsFailedError(PipelineError):
    """Every segment failed to synthesize -- there is nothing to merge."""

    def __init__(self, total_segments: int, failed_segments: List[Dict[str, object]]):
        self.total_segments = total_segments
        self.failed_segments = failed_segments
        lines = [f"All {total_segments} segment(s) failed to synthesize; nothing to merge."]
        for entry in failed_segments:
            lines.append(f"  segment {entry['index']} ({entry['speaker']}): {entry['error']}")
        super().__init__("\n".join(lines))


class MergeFailedError(PipelineError):
    """ffmpeg ran but did not produce an output file."""

    def __init__(self):
        super().__init__(
            "ffmpeg merge failed to produce an output file. Check the server/process "
            "log for ffmpeg's stderr."
        )


@dataclasses.dataclass
class SynthesisResult:
    output_path: Path
    duration_seconds: Optional[float]
    total_segments: int
    succeeded: int
    failed: int
    failed_segments: List[Dict[str, object]]  # [{"index": int, "speaker": str, "error": str}, ...]
    metadata_file: Path
    work_dir: Path


def probe_duration_seconds(path: Path) -> Optional[float]:
    """Best-effort duration lookup via ffprobe. Returns None if ffprobe isn't on PATH or fails."""
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, shell=False, timeout=30,
        )
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def synthesize_to_file(
    transcript: List[Tuple[str, str]],
    output_path: Path,
    work_dir: Path,
    *,
    voice_settings: Optional[Dict[str, str]] = None,
    style_settings: Optional[Dict[str, str]] = None,
    model: Optional[str] = None,
    language_code: Optional[str] = None,
    audio_service: Optional[AudioService] = None,
    progress_callback: Optional[Callable[[int, int, str, int], None]] = None,
) -> SynthesisResult:
    """
    Generate TTS audio for every (speaker, text) segment in `transcript` into
    `work_dir`, merge the results into `output_path`, and return a structured
    result.

    Raises `AllSegmentsFailedError` if every segment failed (nothing to merge)
    or `MergeFailedError` if the ffmpeg merge itself failed. A *partial*
    failure (some, not all, segments failed) is NOT raised -- it comes back on
    `SynthesisResult.failed` / `.failed_segments` so each caller decides how
    loud to be about it (the CLI exits 2; the MCP tool reports it in the
    result). Silent partial success -- reporting a run that lost segments as
    plain success -- is the bug this project already fixed once in the HTTP
    API and once in the skill's CLI; this function's contract exists so a
    third caller can't reintroduce it by omission.
    """
    service = audio_service or get_audio_service()

    audio_result = service.generate_audio_from_transcript(
        transcript,
        work_dir,
        voice_settings=voice_settings,
        style_settings=style_settings,
        model=model,
        language_code=language_code,
        progress_callback=progress_callback,
    )

    total_segments = audio_result["success"] + audio_result["failed"]
    failed_segments = [
        {"index": entry["index"], "speaker": entry["speaker"], "error": entry["error"]}
        for entry in audio_result["audio_files"]
        if not entry["success"]
    ]

    if audio_result["success"] == 0:
        raise AllSegmentsFailedError(total_segments, failed_segments)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_file = Path(audio_result["metadata_file"])
    merged_path = service.merge_audio_files(metadata_file, output_path)

    if not merged_path:
        raise MergeFailedError()

    return SynthesisResult(
        output_path=merged_path,
        duration_seconds=probe_duration_seconds(merged_path),
        total_segments=total_segments,
        succeeded=audio_result["success"],
        failed=audio_result["failed"],
        failed_segments=failed_segments,
        metadata_file=metadata_file,
        work_dir=work_dir,
    )
