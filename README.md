# transcription-skill

An [agent skill](https://agentskills.io) and command-line tool for
transcribing YouTube videos and local video/audio files to text using
Google's [`gemini-3.5-flash`](https://replicate.com/google/gemini-3.5-flash)
on [Replicate](https://replicate.com).

Works with Claude Code, OpenCode, Codex, Pi, or any coding agent that
supports the Agent Skills protocol.

## What it does

Given a YouTube URL, the skill runs this pipeline end to end:

1. Download the video with `yt-dlp` under a slugified filename
2. Extract its audio with `ffmpeg` (stream copy, no re-encoding)
3. Transcribe the audio verbatim with [`google/gemini-3.5-flash`](https://replicate.com/google/gemini-3.5-flash) on Replicate
4. Write the transcript to a `.txt` file

Given a local video file, it starts at step 2. Given a local audio file, it
starts at step 3.

## Install

```sh
npx skills add zeke/transcription-skill
```

Requirements: Python 3, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (for
YouTube URLs), [`ffmpeg`](https://ffmpeg.org) (for video files), and a
[`REPLICATE_API_TOKEN`](https://replicate.com/account/api-tokens). If
`yt-dlp` or `ffmpeg` is missing, the agent will offer to install it (e.g.
via Homebrew) rather than failing outright.

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

## Why gemini-3.5-flash

The skill hardcodes [`gemini-3.5-flash`](https://replicate.com/google/gemini-3.5-flash)
as its transcription model. That choice came from benchmarking it against
[`openai/whisper`](https://replicate.com/openai/whisper) (large-v3) and
three other Gemini variants on Replicate, transcribing the same ~7-minute
narrated video with each and comparing prediction time and transcript
quality.

| Model | predict_time | total_time | Notes |
|---|---:|---:|---|
| **[gemini-3.5-flash](https://replicate.com/google/gemini-3.5-flash)** | **18.6s** | **19.1s** | Fastest by a wide margin. Clean punctuation and paragraphing, accuracy on par with the pro models. |
| [gemini-3-flash](https://replicate.com/google/gemini-3-flash) | 28.2s | 28.7s | Accurate, slightly terser phrasing than 3.5-flash. |
| [gemini-3-pro](https://replicate.com/google/gemini-3-pro) | 35.2s | 35.6s | Natural casing and paragraphing, no accuracy gain over the flash variants to justify the extra time. |
| [gemini-3.1-pro](https://replicate.com/google/gemini-3.1-pro) | 78.3s | 78.7s | Same accuracy as gemini-3-pro, ~4x slower than gemini-3.5-flash for no discernible quality gain. |
| [openai/whisper](https://replicate.com/openai/whisper) (large-v3) | 93.2s | 116.9s | Slowest overall. Dense single-paragraph output, no paragraph breaks, lowercase proper nouns. |
| [google/gemini-2.5-flash](https://replicate.com/google/gemini-2.5-flash) | n/a | n/a | Not testable — this model has no `audio` input on Replicate. |

`gemini-3.5-flash` won on speed (roughly 5x faster than Whisper, 4x faster
than `gemini-3.1-pro`) with no loss in transcript quality, so there was no
reason to reach for a slower or "thinking" model on straightforward
narrated speech. See
[`skills/transcription-skill/SKILL.md`](skills/transcription-skill/SKILL.md)
for the gotchas found while building this (Gemini's inability to fetch
Replicate's own file URLs, `.m4a` mimetype sniffing, etc.).

## License

MIT
