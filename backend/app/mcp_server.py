"""
Local stdio MCP server for Text2Podcast.

Exposes the TTS pipeline (app/services/pipeline.py, backed by
app/services/audio_service.py) as MCP tools so any MCP client -- Claude Code,
Claude Desktop, Cursor, etc. -- can turn a transcript into a two-speaker
podcast MP3 without going through the HTTP API or the Claude Agent Skill.

Like the skill, this server does NOT write the podcast script -- the calling
agent does. It only does text-to-speech and merging, so it needs
`GOOGLE_APPLICATION_CREDENTIALS` and `ffmpeg` on PATH -- no LLM key of any
kind, and no `GEMINI_API_KEY`/`OPENAI_API_KEY`.

This is a **local stdio** server only: no auth, no quotas, no file hosting,
no billing. Turning this into a hosted/remote service is a different (and
currently out of scope) piece of work -- see MCP_DESIGN.md.

Run it directly:
    cd backend && python -m app.mcp_server

Or point an MCP client at it, e.g. in Claude Code's `.mcp.json`:
    {
      "mcpServers": {
        "text2podcast": {
          "command": "python",
          "args": ["-m", "app.mcp_server"],
          "cwd": "/absolute/path/to/Text2Podcast/backend",
          "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": "/absolute/path/to/service-account-key.json"
          }
        }
      }
    }

SDK note (mcp==2.0.0): there is no `mcp.server.fastmcp` / `FastMCP` in this
version -- that's the 1.x API. The ergonomic server class here is
`MCPServer`, from `mcp.server.mcpserver`, and so is the `Context` type
injected into tool functions (NOT `mcp.server.context.Context` -- that's a
different, lower-level class not constructed by the tool-call path; see the
worked note in this repo's design doc for how that was verified).
"""
import asyncio
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.services import pipeline
from app.services.audio_service import get_audio_service

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
VOICE_LIST_PATH = REPO_ROOT / "voice_list.md"


# ---------------------------------------------------------------------------
# Tool argument / result models
# ---------------------------------------------------------------------------
class Segment(BaseModel):
    speaker: str = Field(description='Speaker label, e.g. "Speaker 1".')
    text: str = Field(description="The line of dialogue for this speaker to say.")


class VoiceInfo(BaseModel):
    name: str
    gender: str


class FailedSegment(BaseModel):
    index: int
    speaker: str
    error: str


class SynthesizePodcastResult(BaseModel):
    output_path: str
    duration_seconds: Optional[float] = None
    total_segments: int
    succeeded: int
    failed: int
    partial: bool = Field(description="True iff failed > 0 -- some dialogue is missing from output_path.")
    failed_segments: List[FailedSegment] = Field(default_factory=list)
    segments_dir: str = Field(
        description="Where the per-segment working files and metadata.json were kept, "
                     "for a later regenerate_segment call against this same output_path."
    )
    message: str


class RegenerateSegmentResult(BaseModel):
    output_path: str
    segment_index: int
    regenerated_success: bool
    regenerated_error: Optional[str] = None
    total_segments: int
    succeeded: int
    failed: int
    partial: bool = Field(description="True iff failed > 0 across the whole episode, not just this segment.")
    message: str


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
server = MCPServer(
    name="text2podcast",
    version="1.0.0",
    instructions=(
        "Turn a two-speaker transcript into a podcast MP3 via Google Cloud TTS. "
        "This server does not write scripts -- call it with a transcript you "
        "(or the user) already wrote. Use list_voices to see available voice "
        "names, synthesize_podcast to generate+merge a full episode, and "
        "regenerate_segment to fix one line of an episode you already made "
        "with this server without resynthesizing everything."
    ),
)


def _format_problems(problems: List["pipeline.PreflightProblem"]) -> str:
    lines = ["Cannot run text-to-speech; the following prerequisite check(s) failed:"]
    for problem in problems:
        lines.append(f"- {problem.message}")
        if problem.fix_hint:
            lines.append(f"  Fix: {problem.fix_hint}")
    return "\n".join(lines)


def _load_voice_list() -> List[VoiceInfo]:
    """
    Parse voice_list.md at the repo root (tab-separated: name, gender, one
    header row) rather than duplicating the voice table into code, so this
    tool always reflects whatever voice_list.md documents.
    """
    if not VOICE_LIST_PATH.is_file():
        raise ToolError(f"voice_list.md not found at {VOICE_LIST_PATH}")

    lines = VOICE_LIST_PATH.read_text(encoding="utf-8").splitlines()
    voices: List[VoiceInfo] = []
    for line in lines[1:]:  # skip the header row ("名稱\t性別")
        parts = line.split("\t")
        name = parts[0].strip() if parts else ""
        if not name:
            continue
        gender = parts[1].strip() if len(parts) > 1 else ""
        voices.append(VoiceInfo(name=name, gender=gender))
    return voices


@server.tool()
async def list_voices() -> List[VoiceInfo]:
    """List the Google Cloud TTS voices available for synthesize_podcast/regenerate_segment,
    with each voice's name and gender, read live from voice_list.md at the repo root."""
    return _load_voice_list()


@server.tool()
async def synthesize_podcast(
    segments: List[Segment],
    output_path: str,
    voices: Optional[Dict[str, str]] = None,
    styles: Optional[Dict[str, str]] = None,
    model: Optional[str] = None,
    language: Optional[str] = None,
    ctx: Context = None,
) -> SynthesizePodcastResult:
    """Synthesize a two-speaker podcast MP3 from a transcript and merge it to output_path.

    segments: the transcript, as an ordered list of {speaker, text}. Written by the
        calling agent -- this tool does not generate dialogue.
    output_path: absolute filesystem path to write the merged MP3 to.
    voices: optional per-speaker voice name overrides, e.g. {"Speaker 1": "Kore"}.
        Speakers not given fall back to the server defaults (Speaker 1=Kore,
        Speaker 2=Charon). See list_voices for available names.
    styles: optional per-speaker TTS steerability prompt, e.g.
        {"Speaker 1": "Speak warmly and conversationally"}. Each value is capped at
        200 characters. Speakers not given get a neutral default prompt.
    model / language: optional TTS model / language code overrides.

    Long transcripts report progress via MCP progress notifications as each
    segment finishes, and this call blocks until the whole episode is done --
    there is no separate polling tool.

    A run that loses segments still produces output_path (missing only the
    failed lines) but is reported with partial=true and failed_segments
    naming exactly which lines are missing -- check `partial` before treating
    a response as a complete episode.
    """
    if not segments:
        raise ValueError("segments must be non-empty")

    output = Path(output_path)
    if not output.is_absolute():
        raise ValueError(f"output_path must be an absolute path, got {output_path!r}")

    pipeline.validate_style_settings(styles)

    problems = pipeline.check_prerequisites()
    if problems:
        raise ToolError(_format_problems(problems))

    transcript = [(segment.speaker, segment.text) for segment in segments]
    voice_settings = pipeline.resolve_voice_settings(voices)
    style_settings = pipeline.resolve_style_settings(styles)

    work_dir = pipeline.segments_dir_for(output)
    # Fresh run: don't let a previous run's leftover segment files (a
    # different segment count, a deleted-then-recreated episode, ...) mix
    # into this one's metadata.json.
    shutil.rmtree(work_dir, ignore_errors=True)

    loop = asyncio.get_running_loop()

    def on_progress(completed: int, total_count: int, speaker: str, index: int) -> None:
        # Called on the worker thread generate_audio_from_transcript runs in
        # (see asyncio.to_thread below) -- report_progress is a coroutine that
        # must run on the event loop, so hand it back via
        # run_coroutine_threadsafe rather than awaiting it here directly.
        if ctx is None:
            return
        asyncio.run_coroutine_threadsafe(
            ctx.report_progress(
                completed, total_count, f"Synthesized segment {index}/{total_count} ({speaker})"
            ),
            loop,
        )

    try:
        result = await asyncio.to_thread(
            pipeline.synthesize_to_file,
            transcript,
            output,
            work_dir,
            voice_settings=voice_settings,
            style_settings=style_settings,
            model=model,
            language_code=language,
            progress_callback=on_progress,
        )
    except pipeline.AllSegmentsFailedError as e:
        raise ToolError(str(e)) from e
    except pipeline.MergeFailedError as e:
        raise ToolError(str(e)) from e

    if result.failed:
        message = (
            f"WARNING: {result.failed} of {result.total_segments} segment(s) failed to "
            f"synthesize. {result.output_path.name} is missing that dialogue -- see "
            "failed_segments for exactly which lines."
        )
    else:
        message = f"Podcast synthesized: {result.succeeded}/{result.total_segments} segments, all succeeded."

    return SynthesizePodcastResult(
        output_path=str(result.output_path),
        duration_seconds=result.duration_seconds,
        total_segments=result.total_segments,
        succeeded=result.succeeded,
        failed=result.failed,
        partial=result.failed > 0,
        failed_segments=[FailedSegment(**entry) for entry in result.failed_segments],
        segments_dir=str(result.work_dir),
        message=message,
    )


@server.tool()
async def regenerate_segment(
    output_path: str,
    segment_index: int,
    text: Optional[str] = None,
    voice: Optional[str] = None,
    style_prompt: Optional[str] = None,
    ctx: Context = None,
) -> RegenerateSegmentResult:
    """Regenerate exactly one segment of an episode previously produced by
    synthesize_podcast, then re-merge the full audio at output_path.

    output_path: the episode to repair -- must be the same absolute path
        synthesize_podcast was called with. Its working files (per-segment
        audio + metadata.json) must still exist alongside it; if they were
        cleaned up, this raises rather than silently resynthesizing the
        whole episode.
    segment_index: 1-based index into the original transcript.
    text / voice / style_prompt: optional overrides for just this segment;
        each falls back to what was used originally when omitted (style_prompt
        falls back to the server's neutral default, since per-segment style
        isn't persisted from the original run). style_prompt is capped at
        200 characters.
    """
    output = Path(output_path)
    if not output.is_absolute():
        raise ValueError(f"output_path must be an absolute path, got {output_path!r}")

    if style_prompt is not None and len(style_prompt) > pipeline.MAX_STYLE_PROMPT_LENGTH:
        raise ValueError(f"style_prompt exceeds {pipeline.MAX_STYLE_PROMPT_LENGTH} characters")

    problems = pipeline.check_prerequisites()
    if problems:
        raise ToolError(_format_problems(problems))

    metadata_file = pipeline.metadata_file_for(output)
    if not metadata_file.exists():
        raise ToolError(
            f"No working files found for {output}. Expected metadata at {metadata_file}, "
            f"in the segments directory {metadata_file.parent}. This episode either wasn't "
            "produced by this server's synthesize_podcast tool, or its working directory was "
            "deleted since. Re-run synthesize_podcast to produce fresh working files before "
            "regenerating a segment."
        )

    service = get_audio_service()

    if ctx is not None:
        await ctx.report_progress(0, 2, f"Regenerating segment {segment_index}...")

    try:
        regen_result = await asyncio.to_thread(
            service.regenerate_segment, metadata_file, segment_index, text, voice, style_prompt
        )
    except ValueError as e:
        raise ToolError(str(e)) from e

    if ctx is not None:
        await ctx.report_progress(1, 2, "Merging audio files...")

    merged_path = await asyncio.to_thread(service.merge_audio_files, metadata_file, output)
    if not merged_path:
        raise ToolError("ffmpeg merge failed to produce an output file after regenerating the segment.")

    if ctx is not None:
        await ctx.report_progress(2, 2, "Done")

    if not regen_result["regenerated_success"]:
        message = (
            f"Segment {segment_index} failed to regenerate: {regen_result['regenerated_error']}. "
            f"{regen_result['failed']} of {regen_result['total_segments']} segment(s) in this "
            "episode are now missing dialogue."
        )
    elif regen_result["failed"]:
        message = (
            f"Segment {segment_index} regenerated successfully, but {regen_result['failed']} other "
            f"segment(s) in this episode ({regen_result['total_segments']} total) are still failed "
            "from before."
        )
    else:
        message = f"Segment {segment_index} regenerated successfully."

    return RegenerateSegmentResult(
        output_path=str(merged_path),
        segment_index=segment_index,
        regenerated_success=regen_result["regenerated_success"],
        regenerated_error=regen_result["regenerated_error"],
        total_segments=regen_result["total_segments"],
        succeeded=regen_result["success"],
        failed=regen_result["failed"],
        partial=regen_result["failed"] > 0,
        message=message,
    )


if __name__ == "__main__":
    server.run(transport="stdio")
