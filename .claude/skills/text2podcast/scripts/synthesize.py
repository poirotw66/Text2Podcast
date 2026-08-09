#!/usr/bin/env python3
"""
CLI wrapper around backend/app/services/audio_service.py for the text2podcast
Claude Agent Skill.

This script does NOT reimplement text-to-speech or audio merging -- it imports
and calls the real service module the FastAPI backend uses, so there is exactly
one place that knows how to talk to Google Cloud TTS and how segments get
stitched together. See the "Locate the repo" section below for how the import
is wired up without adding this skill's directory to the backend's package.

Usage:
    python synthesize.py --transcript FILE --output FILE
                          [--voice "Speaker 1=Kore"] [--voice "Speaker 2=Charon"]
                          [--style "Speaker 1=Speak warmly and conversationally"]
                          [--language cmn-tw] [--model MODEL] [--keep-segments]

Exit codes:
    0  every segment synthesized successfully; --output was written.
    1  hard failure: bad arguments, a preflight check failed, or no output file
       could be produced at all.
    2  --output was written, but at least one segment failed. The failed
       segment indices and their errors are printed to stderr.
"""
import argparse
import os
import shutil
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, NoReturn, Optional, Tuple

SCRIPT_PATH = Path(__file__).resolve()
# .../<repo>/.claude/skills/text2podcast/scripts/synthesize.py
#      [4]      [3]    [2]        [1]        [0]
REPO_ROOT = SCRIPT_PATH.parents[4]
BACKEND_DIR = REPO_ROOT / "backend"

REPO_LAYOUT_ERROR = f"""\
Could not find a Text2Podcast backend at {BACKEND_DIR}.

This skill ships as part of a Text2Podcast checkout and reuses
backend/app/services/audio_service.py directly -- it has no vendored copy of
the TTS/merge logic and does not fall back to one. Make sure this script is
still located at <repo>/.claude/skills/text2podcast/scripts/synthesize.py
inside a full clone of the Text2Podcast repository (i.e. backend/app/services/
must exist as a sibling of .claude/), then try again.
"""

GOOGLE_CLOUD_TTS_ERROR = """\
The `google-cloud-texttospeech` package is not installed in this Python
environment.

Fix: install the backend's pinned dependencies, e.g.
    pip install -r {req}
(or at minimum: pip install google-cloud-texttospeech==2.37.0)
""".format(req=BACKEND_DIR / "requirements.txt")


def _fail(message: str) -> NoReturn:
    print(message.rstrip("\n"), file=sys.stderr)
    sys.exit(1)


def _load_backend_modules():
    """
    Add <repo>/backend to sys.path and import the two backend modules this
    script needs. Exits with an actionable message (rather than a raw
    traceback) if either step fails -- distinguishing "not inside a
    Text2Podcast checkout" from "google-cloud-texttospeech isn't installed",
    since those need different fixes.
    """
    if not (BACKEND_DIR / "app" / "services" / "audio_service.py").exists():
        _fail(REPO_LAYOUT_ERROR)

    sys.path.insert(0, str(BACKEND_DIR))

    try:
        # file_handler.py is stdlib-only (json/ast/pathlib), so if importing
        # even this fails, the problem is the checkout/sys.path, not a
        # missing third-party dependency.
        import app.utils.file_handler as file_handler  # noqa: F401
    except ImportError as e:
        _fail(f"{REPO_LAYOUT_ERROR}\n(underlying error: {e})")

    try:
        import google.cloud.texttospeech  # noqa: F401
    except ImportError:
        _fail(GOOGLE_CLOUD_TTS_ERROR)

    try:
        import app.services.audio_service as audio_service
    except ImportError as e:
        _fail(
            "Unexpected error importing app.services.audio_service even though "
            f"the repo layout and google-cloud-texttospeech both look fine: {e}"
        )

    return file_handler, audio_service


def _check_ffmpeg(audio_service_module) -> None:
    """
    Reuse audio_service's own ffmpeg check (it already raises a clear
    RuntimeError naming the fix) instead of duplicating the shutil.which()
    logic here.
    """
    try:
        audio_service_module._require_ffmpeg()
    except RuntimeError as e:
        _fail(str(e))


def _check_credentials() -> None:
    """
    Fail fast, before any paid TTS calls, if there's no way to authenticate to
    Google Cloud: either GOOGLE_APPLICATION_CREDENTIALS pointing at a real
    file, or ambient Application Default Credentials (e.g. from
    `gcloud auth application-default login`, or a GCE/Cloud Run metadata
    server).
    """
    cred_path_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path_str:
        cred_path = Path(cred_path_str)
        if not cred_path.is_file():
            _fail(
                f"GOOGLE_APPLICATION_CREDENTIALS is set to '{cred_path_str}', but "
                "that file does not exist.\n"
                "Fix: point it at a valid Google Cloud service-account key JSON "
                "file, e.g.\n"
                "    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json"
            )
        return

    try:
        import google.auth

        google.auth.default()
    except Exception as e:
        _fail(
            "No Google Cloud credentials found (GOOGLE_APPLICATION_CREDENTIALS is "
            "not set, and no Application Default Credentials are available).\n"
            "Fix: either\n"
            "    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json\n"
            "  or\n"
            "    gcloud auth application-default login\n"
            f"(underlying error: {e})"
        )


def _parse_pair(raw: str, flag: str) -> Tuple[str, str]:
    """Parse a repeatable 'Speaker=Value' CLI argument, e.g. --voice/--style."""
    if "=" not in raw:
        _fail(
            f"Invalid {flag} value {raw!r}: expected the form 'Speaker=Value', "
            f'e.g. {flag} "Speaker 1=Kore".'
        )
    speaker, _, value = raw.partition("=")
    speaker, value = speaker.strip(), value.strip()
    if not speaker or not value:
        _fail(
            f"Invalid {flag} value {raw!r}: both the speaker and the value must "
            f'be non-empty, e.g. {flag} "Speaker 1=Kore".'
        )
    return speaker, value


def _ffprobe_duration_seconds(path: Path) -> Optional[float]:
    """Best-effort duration lookup via ffprobe. Returns None if unavailable."""
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


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown (ffprobe not found on PATH)"
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m{secs:02d}s ({seconds:.1f}s)"


class _ExitCode1ArgumentParser(argparse.ArgumentParser):
    """
    argparse's default ArgumentParser.error() exits with code 2, which would
    collide with this script's own "merge succeeded but some segments failed"
    exit code -- a caller branching on exit code could mistake a plain typo in
    --voice for a partial-synthesis failure worth retrying. Bad arguments are
    a hard failure (exit 1) here; -h/--help still exits 0 as normal, since
    that path never reaches error().
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _ExitCode1ArgumentParser(
        prog="synthesize.py",
        description=(
            "Synthesize a two-speaker podcast MP3 from a transcript JSON file, "
            "using Google Cloud TTS via backend/app/services/audio_service.py."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python synthesize.py --transcript transcript.json --output podcast.mp3

  python synthesize.py --transcript transcript.json --output podcast.mp3 \\
      --voice "Speaker 1=Kore" --voice "Speaker 2=Charon" \\
      --style "Speaker 1=Speak warmly and conversationally"

  python synthesize.py --transcript transcript.json --output podcast.mp3 --keep-segments
""",
    )
    parser.add_argument(
        "--transcript", required=True, type=Path,
        help="Path to a transcript JSON file: [{\"speaker\": \"Speaker 1\", \"text\": \"...\"}, ...] "
             "(the format app.utils.file_handler.save_transcript writes).",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Path to write the merged podcast MP3 to.",
    )
    parser.add_argument(
        "--voice", action="append", default=[], metavar="Speaker=Voice",
        help="Voice for one speaker, e.g. \"Speaker 1=Kore\". Repeatable. "
             "Speakers not given fall back to the module defaults "
             "(Speaker 1=Kore, Speaker 2=Charon). See voice_list.md at the repo root.",
    )
    parser.add_argument(
        "--style", action="append", default=[], metavar="Speaker=Style prompt",
        help="TTS steerability prompt for one speaker, e.g. "
             "\"Speaker 1=Speak warmly and conversationally\". Repeatable. "
             "Speakers not given fall back to the module default prompt.",
    )
    parser.add_argument(
        "--language", default=None,
        help="TTS language code (default: the module's LANGUAGE_CODE, currently cmn-tw).",
    )
    parser.add_argument(
        "--model", default=None,
        help="TTS model name (default: the module's TTS_MODEL, "
             "currently gemini-3.1-flash-tts-preview unless overridden by the TTS_MODEL env var).",
    )
    parser.add_argument(
        "--keep-segments", action="store_true",
        help="Keep the per-segment MP3s and metadata.json after merging, and print "
             "their directory. By default this working directory is deleted once "
             "the merge succeeds, leaving only --output.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.transcript.is_file():
        print(f"Transcript file not found: {args.transcript}", file=sys.stderr)
        return 1

    # _parse_pair calls sys.exit(1) via _fail() on a malformed pair, after
    # printing an actionable message -- nothing to catch here.
    voice_overrides: Dict[str, str] = dict(_parse_pair(v, "--voice") for v in args.voice)
    style_overrides: Dict[str, str] = dict(_parse_pair(s, "--style") for s in args.style)

    file_handler, audio_service = _load_backend_modules()
    _check_ffmpeg(audio_service)
    _check_credentials()

    try:
        transcript_pairs = file_handler.load_transcript(args.transcript)
    except (ValueError, OSError) as e:
        print(f"Could not read transcript {args.transcript}: {e}", file=sys.stderr)
        return 1

    if not transcript_pairs:
        print(f"Transcript {args.transcript} contains no segments.", file=sys.stderr)
        return 1

    # Seed with the module's own defaults, then layer CLI overrides on top --
    # generate_audio_from_transcript() would otherwise fall back an *unmapped*
    # speaker in a partial voice_settings dict straight to a hardcoded "Kore"
    # rather than DEFAULT_SPEAKER_VOICES, so a partial --voice would silently
    # override more than the user asked for. Seeding here keeps "unspecified
    # speakers fall back to the module defaults" true.
    voice_settings = dict(audio_service.DEFAULT_SPEAKER_VOICES)
    voice_settings.update(voice_overrides)
    style_settings = dict(style_overrides)

    work_dir = Path(tempfile.mkdtemp(prefix="text2podcast-segments-"))

    try:
        service = audio_service.get_audio_service()
        result = service.generate_audio_from_transcript(
            [(speaker, text) for speaker, text in transcript_pairs],
            work_dir,
            voice_settings=voice_settings,
            style_settings=style_settings,
            model=args.model,
            language_code=args.language,
        )

        total_segments = result["success"] + result["failed"]

        if result["success"] == 0:
            print(
                f"All {total_segments} segment(s) failed to synthesize; nothing to merge.",
                file=sys.stderr,
            )
            for entry in result["audio_files"]:
                if not entry["success"]:
                    print(f"  segment {entry['index']} ({entry['speaker']}): {entry['error']}", file=sys.stderr)
            return 1

        args.output.parent.mkdir(parents=True, exist_ok=True)
        merged_path = service.merge_audio_files(Path(result["metadata_file"]), args.output)

        if not merged_path:
            print("ffmpeg merge failed to produce an output file. See the log above for ffmpeg's stderr.", file=sys.stderr)
            return 1

        duration = _format_duration(_ffprobe_duration_seconds(merged_path))
        voices_used = ", ".join(f"{speaker}={voice}" for speaker, voice in sorted(voice_settings.items()))

        print(f"Output:   {merged_path}")
        print(f"Duration: {duration}")
        print(f"Segments: {result['success']} succeeded, {result['failed']} failed, {total_segments} total")
        print(f"Voices:   {voices_used}")

        if result["failed"] > 0:
            print("", file=sys.stderr)
            print(
                f"WARNING: {result['failed']} of {total_segments} segment(s) failed. "
                f"{merged_path.name} is missing that dialogue.",
                file=sys.stderr,
            )
            for entry in result["audio_files"]:
                if not entry["success"]:
                    print(f"  segment {entry['index']} ({entry['speaker']}): {entry['error']}", file=sys.stderr)
            return 2

        return 0
    finally:
        if args.keep_segments:
            print(f"Segment files kept at: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
