#!/usr/bin/env python3
"""
CLI wrapper around backend/app/services/pipeline.py for the text2podcast
Claude Agent Skill.

This script does NOT reimplement text-to-speech, audio merging, preflight
checks, or voice/style default-resolution -- it imports and calls the real
pipeline module the backend uses (app/services/pipeline.py, itself a thin
orchestration layer over app/services/audio_service.py), so there is exactly
one place that knows how to talk to Google Cloud TTS, how segments get
stitched together, and what "missing prerequisite" or "partial failure"
means. See the "Locate the repo" section below for how the import is wired
up without adding this skill's directory to the backend's package.

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
import shutil
import sys
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
backend/app/services/pipeline.py directly -- it has no vendored copy of the
TTS/merge logic and does not fall back to one. Make sure this script is
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
    Add <repo>/backend to sys.path and import the backend modules this
    script needs. Exits with an actionable message (rather than a raw
    traceback) if either step fails -- distinguishing "not inside a
    Text2Podcast checkout" from "google-cloud-texttospeech isn't installed",
    since those need different fixes.

    The google-cloud-texttospeech import check has to happen here, standalone,
    *before* importing app.services.pipeline: pipeline.py imports
    app.services.audio_service, which imports google.cloud.texttospeech
    unconditionally at module level, so without this standalone check first, a
    missing package would surface as a confusing failure two imports removed
    from this actionable message instead of this one.
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
        import app.services.pipeline as pipeline
    except ImportError as e:
        _fail(
            "Unexpected error importing app.services.pipeline even though "
            f"the repo layout and google-cloud-texttospeech both look fine: {e}"
        )

    return file_handler, pipeline


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
            "using Google Cloud TTS via backend/app/services/pipeline.py."
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

    file_handler, pipeline = _load_backend_modules()

    problems = pipeline.check_prerequisites()
    if problems:
        for problem in problems:
            print(problem.message, file=sys.stderr)
            if problem.fix_hint:
                print(problem.fix_hint, file=sys.stderr)
        return 1

    try:
        transcript_pairs = file_handler.load_transcript(args.transcript)
    except (ValueError, OSError) as e:
        print(f"Could not read transcript {args.transcript}: {e}", file=sys.stderr)
        return 1

    if not transcript_pairs:
        print(f"Transcript {args.transcript} contains no segments.", file=sys.stderr)
        return 1

    # Seed with the module's own defaults, then layer CLI overrides on top --
    # see resolve_voice_settings()'s docstring for why this matters (a partial
    # --voice must not silently blow away another speaker's default voice).
    voice_settings = pipeline.resolve_voice_settings(voice_overrides)
    style_settings = pipeline.resolve_style_settings(style_overrides)

    work_dir = Path(tempfile.mkdtemp(prefix="text2podcast-segments-"))

    try:
        try:
            result = pipeline.synthesize_to_file(
                [(speaker, text) for speaker, text in transcript_pairs],
                args.output,
                work_dir,
                voice_settings=voice_settings,
                style_settings=style_settings,
                model=args.model,
                language_code=args.language,
            )
        except pipeline.AllSegmentsFailedError as e:
            print(str(e), file=sys.stderr)
            return 1
        except pipeline.MergeFailedError as e:
            print(str(e), file=sys.stderr)
            return 1

        duration = _format_duration(result.duration_seconds)
        voices_used = ", ".join(f"{speaker}={voice}" for speaker, voice in sorted(voice_settings.items()))

        print(f"Output:   {result.output_path}")
        print(f"Duration: {duration}")
        print(f"Segments: {result.succeeded} succeeded, {result.failed} failed, {result.total_segments} total")
        print(f"Voices:   {voices_used}")

        if result.failed > 0:
            print("", file=sys.stderr)
            print(
                f"WARNING: {result.failed} of {result.total_segments} segment(s) failed. "
                f"{result.output_path.name} is missing that dialogue.",
                file=sys.stderr,
            )
            for entry in result.failed_segments:
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
