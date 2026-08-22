# transcription-skill

An [agent skill](https://agentskills.io) and command-line tool for
transcribing YouTube videos and local video/audio files to text using
Google's `gemini-3.5-flash` on [Replicate](https://replicate.com).

Works with Claude Code, OpenCode, Codex, Pi, or any coding agent that
supports the Agent Skills protocol.

## Capabilities

- Download a YouTube video with `yt-dlp` under a slugified filename
- Extract audio from any video file with `ffmpeg`
- Transcribe audio verbatim with `google/gemini-3.5-flash` on Replicate
- Works as a single command from a YouTube URL straight to a `.txt` transcript

## Install

```sh
npx skills add zeke/transcription-skill
```

## Try it

Once installed, invoke the skill by pasting a prompt like this into your
coding agent:

```text
Transcribe this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Or run the script directly:

```sh
export REPLICATE_API_TOKEN=...
python3 skills/transcription-skill/scripts/transcribe.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Requirements: Python 3, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (for
YouTube URLs), [`ffmpeg`](https://ffmpeg.org) (for video files), and a
[`REPLICATE_API_TOKEN`](https://replicate.com/account/api-tokens).

## Why gemini-3.5-flash

This skill's model choice came from benchmarking `openai/whisper`
(large-v3) against four Gemini variants on Replicate for speed and
transcript quality on real narrated video. `gemini-3.5-flash` won on
speed by a wide margin with no loss in accuracy. See
[`skills/transcription-skill/SKILL.md`](skills/transcription-skill/SKILL.md)
for the full writeup and the gotchas found along the way.

## License

MIT
