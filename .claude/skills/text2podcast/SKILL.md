---
name: text2podcast
description: "Turn an article, notes, or a document into a two-speaker podcast MP3. Use whenever the user wants to convert text, a file, a webpage, or pasted writing into a spoken podcast episode, an audio dialogue, or a two-host discussion, or asks to \"turn this into a podcast\" / \"make an audio version\" / \"generate a podcast episode\" from content they provide."
---

# Text2Podcast

Turns text into a two-speaker podcast MP3, entirely inside this conversation.

## Why this is different from the Text2Podcast web app

This skill runs inside Claude, so **Claude writes the dialogue script itself** —
there is no call out to an LLM API for that step. The only external API this
skill uses is Google Cloud Text-to-Speech, to turn the finished script into
audio. That means:

- The only credential this skill needs is `GOOGLE_APPLICATION_CREDENTIALS`
  (a Google Cloud service-account key). No `GEMINI_API_KEY`, no
  `OPENAI_API_KEY`, no `google-genai` / `openai` SDKs, no FastAPI server.
- Script writing is conversational: show the draft, take notes, revise, and
  only spend TTS quota once the user is happy with it (see step 4).

Audio synthesis and merging reuse `backend/app/services/audio_service.py`
exactly as the web app does, via `scripts/synthesize.py` in this skill — there
is no separate/vendored copy of that logic to fall out of sync.

## Workflow

### 1. Get the source text

Ask for (or accept) either a file path/pasted document, or text pasted
directly into the conversation. Read the file yourself if a path is given.

### 2. Choose a length

Ask which length the user wants, or infer a sensible one from how much source
material there is. These are the three modes this project has always used
(from `backend/app/prompts.py`, `TRANSCRIPT_WRITER_PROMPT`) — carry over the
real targets, don't invent new ones:

| Mode   | Runtime  | Word count      | Dialogue turns |
|--------|----------|------------------|----------------|
| SHORT  | ~7 min   | 1,500–1,800 字   | 20–25          |
| MEDIUM | ~15 min  | 3,000–3,500 字   | 40–50          |
| LONG   | ~30 min  | 6,000–7,000 字   | 80–100         |

(Word counts are for Chinese-language output, matching `LANGUAGE_CODE =
"cmn-tw"` — the project's target language. If you and the user are writing in
another language, treat these as pacing/turn-count targets rather than literal
character counts.)

### 3. Write the two-speaker dialogue

This is the step that replaces the web app's Step 1 (LLM script draft) and
Step 2 (TTS-oriented rewrite) — write the finished script directly, in one
pass, following the craft rules below (ported from `TRANSCRIPT_WRITER_PROMPT`
and `TRANSCRIPT_REWRITER_PROMPT` in `backend/app/prompts.py`).

**Speaker roles:**

- **Speaker 1** leads the conversation and teaches Speaker 2. A charismatic
  storyteller who reaches for real-world analogies, history, and pop culture
  to explain things. Opens the episode by giving it a punchy, clickbait-ish
  title on the fly.
- **Speaker 2** is a total newcomer to the topic. Keeps the conversation on
  track by asking follow-up questions — sometimes excited, sometimes clearly
  confused. Interrupts often ("huh?", "wait, so you're saying...?"). Every so
  often goes on a bold, slightly-outlandish but entertaining tangent, which
  Speaker 1 eventually pulls back on topic.

**Dialogue style:**

- 100% dialogue — no narration, no scene-setting, no section headers, no
  standalone episode title outside of Speaker 1's spoken intro.
- Write it like a *real, recorded* episode: natural interruptions, filler
  words ("um", "oh", "right", "wait"), genuine back-and-forth — not a lecture
  read aloud.
- Explanations get interrupted and the response after the interruption gets
  fully developed, not glossed over.
- Questions come with concrete, real-world examples, and Speaker 1 digs into
  the details of those examples rather than name-checking them.
- Hit the target word count / turn count for the chosen length mode. Too
  short under-fills the runtime; too long overshoots it. If you're short,
  expand with more detail, analogies, and follow-up questions rather than
  padding; if you're running long, wrap up rather than introducing new ground.

**Expressive markers — use these by default.** This project's TTS pipeline
(Google Cloud TTS via the Gemini TTS models) is steered by bracketed markers
inside the dialogue text, exactly as the web app writes them. Use them
throughout the script, the same way the web app does:

- **Non-verbal sounds (use these often — most reliable, most impactful):**
  `[sigh]`, `[laughing]`, `[uhm]` — confusion, surprise, thinking, hesitation,
  amusement, emphasis. Speaker 1: roughly once every 5–7 lines (emphasis,
  thinking, storytelling beats). Speaker 2: roughly once every 2–3 lines
  (questions, surprise, confusion) — Speaker 2 is the more reactive character.
- **Style modifiers (use as the moment calls for it):** `[sarcasm]`,
  `[shouting]`, `[whispering]`, `[extremely fast]` — sarcasm/humor, emphasis or
  excitement, secrecy or a dramatic beat, excitement or urgency.
- **Pacing and pauses (use sparingly):** `[short pause]` (~250ms, like a
  comma), `[medium pause]` (~500ms, between ideas or a topic change),
  `[long pause]` (~1000ms+, dramatic emphasis — at most once every 10–15
  lines).

A marker's emotional register must match the words around it — don't drop one
in just to have used it. Example of the target density and placement:

```
Speaker 1: Welcome back to the show! [medium pause] Today we're diving into
something that just broke the internet. [short pause] I'm talking about the
new model release, [shouting] and honestly, this is a huge deal.
Speaker 2: [uhm] Okay wait, I'm already lost. [laughing] What actually makes
it different from the last one?
```

If the user asks for plain dialogue without these markers, that's a fine
creative choice — just leave them out for that script.

### 4. Review with the user before synthesizing

**Show the full script to the user before running TTS.** This is the main
advantage of the skill flow over the web app's Step 2/3 editing UI — iterate
on wording, pacing, and tone conversationally, for free, before spending
Google Cloud TTS quota. Treat this as a required step, not an optional
courtesy: don't synthesize on the first draft without asking.

### 5. Pick voices

There are 30 Google Cloud TTS voices available, listed with their genders in
[`voice_list.md`](../../../voice_list.md) at the repo root — read that file
for the options rather than guessing names. Ask the user for a preference per
speaker, or pick a reasonable pair yourself (the module defaults are
Speaker 1 = Kore, Speaker 2 = Charon) and mention what you picked.

You can also set a per-speaker style prompt (steers overall tone, separately
from the in-line markers), e.g. "Speak in a warm, engaging, and authoritative
tone like a knowledgeable teacher" for Speaker 1, or "React with genuine
curiosity and excitement" for Speaker 2.

### 6. Write the transcript JSON and run synthesize.py

Write the finalized script to a temp file as JSON:

```json
[
  {"speaker": "Speaker 1", "text": "Welcome back to the show! [medium pause] ..."},
  {"speaker": "Speaker 2", "text": "[uhm] Okay wait, I'm already lost. ..."}
]
```

Then run:

```bash
python .claude/skills/text2podcast/scripts/synthesize.py \
  --transcript /path/to/transcript.json \
  --output /path/to/podcast.mp3 \
  --voice "Speaker 1=Kore" --voice "Speaker 2=Charon" \
  --style "Speaker 1=Speak warmly and conversationally"
```

`--voice` and `--style` are repeatable; omit a speaker to use the module
defaults. See `scripts/synthesize.py --help` for the full flag list
(`--language`, `--model`, `--keep-segments`).

### 7. Report the result

Check the exit code:

- **0** — full success. Report the output path, duration, and voices used.
- **2** — the MP3 was still produced, but one or more segments failed (the
  script prints which line indices and why). **Do not present this as a
  finished podcast without saying so** — this mirrors a bug that was just
  fixed in the web app, where a partial failure could silently look like a
  complete episode. Tell the user exactly which lines are missing, show the
  errors, and offer to retry just those segments (re-run `synthesize.py` with
  a transcript containing only the failed lines, then splice/re-merge, or
  simply re-run the whole synthesis if that's simpler).
- **1** — hard failure before or during synthesis (bad arguments, a missing
  dependency, no credentials, or every segment failed). The script's stderr
  names the actual fix (install ffmpeg, install
  `google-cloud-texttospeech`, set `GOOGLE_APPLICATION_CREDENTIALS`, etc.) —
  relay that to the user rather than guessing.
