## About this project

This repo is a published, shareable agent skill and dependency-free Python
CLI for transcribing YouTube videos and local video/audio files. The
installable payload lives in `skills/transcription-skill/`: `SKILL.md` is
the skill itself (for agents), `scripts/transcribe.py` is the CLI, and the
root `README.md` is for humans.

## Keep it portable

This skill is used by many people with different setups.

- Don't hardcode file paths, tokens, or personal CLI tools.
- The CLI must keep running on the Python standard library only. No pip
  install step for end users.
- `yt-dlp` and `ffmpeg` are external requirements, invoked as subprocesses;
  don't add more external tool dependencies without strong reason.

## Time ranges

`--from`/`--to` clip the transcribed range. For YouTube URLs the cut
happens in `yt-dlp` via `--download-sections` so the clip is all that gets
transferred; for local files it happens in `ffmpeg`. Keep those two paths
from double-trimming: `main()` tracks whether the download already applied
the range. ffmpeg cuts use `-ss` before `-i` plus `-t`, not `-to`, because
`-to` would be measured from the seek point.

## Model choice

The skill hardcodes `google/gemini-3.5-flash` as the transcription model,
chosen after benchmarking it against `openai/whisper` (large-v3) and three
other Gemini variants (`gemini-3-pro`, `gemini-3.1-pro`, `gemini-3-flash`)
for speed and quality. If Replicate ships a clearly better/faster model,
re-benchmark before changing `MODEL` in `scripts/transcribe.py`, and update
the "Why gemini-3.5-flash" section in `SKILL.md` with the new reasoning.

Always resolve the model's `latest_version` from the Replicate API at call
time rather than hardcoding a version id.

## Tests

Run `script/test`, which does a syntax/import check of `transcribe.py`
(`python3 -m py_compile`) plus argument-parsing, timestamp, and clip-naming
unit tests. Tests must not require network access, `REPLICATE_API_TOKEN`,
`yt-dlp`, or `ffmpeg`.

## Keeping this file current

Update this AGENTS.md whenever the project's structure, model choice, or
conventions change in a way that future edits should know about.
