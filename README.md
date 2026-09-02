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
starts at step 3. To transcribe only part of something, see
[Transcribing part of a video](#transcribing-part-of-a-video).

## Transcribing part of a video

Most of the time you don't want a whole two-hour podcast transcribed. You
want the 90 seconds where someone said the interesting thing. Ask your
agent for a range and it will pass one through:

```text
Transcribe 15:08 to 16:22 of https://www.youtube.com/watch?v=Ko_-qDCRIAM
```

Or use the flags directly:

```sh
python3 skills/transcription-skill/scripts/transcribe.py "https://www.youtube.com/watch?v=Ko_-qDCRIAM" --from 15:08 --to 16:22
```

Times can be written as `SS`, `MM:SS`, or `HH:MM:SS`. Either flag works on
its own: `--from 15:08` runs to the end of the media, `--to 16:22` starts
from the beginning.

For a YouTube URL the cut happens during the download, via `yt-dlp`'s
`--download-sections`, so only the range you asked for crosses the network.
Pulling that 74-second clip out of a 108-minute interview transfers about
23 MB rather than the whole video, and the transcript comes back in about
17 seconds because the model only ever sees 74 seconds of audio. Local
video and audio files are cut the same way with `ffmpeg`, which is why
`ffmpeg` is needed for ranges even when the input is already audio.

Clips are named after their range, so they sit alongside full-length
artifacts instead of replacing them:

```
what-did-jeff-bridges-learn-at-death-s-door-ko-qdcriam-15m08s-16m22s.mp4
what-did-jeff-bridges-learn-at-death-s-door-ko-qdcriam-15m08s-16m22s.m4a
what-did-jeff-bridges-learn-at-death-s-door-ko-qdcriam-15m08s-16m22s.txt
```

Ranges are checked against the media's real duration before anything is
downloaded or cut. Asking for a range that starts after the media ends
fails immediately, in about two seconds for a YouTube URL, without writing
any files. Asking for one that merely runs past the end warns and
transcribes up to the end.

That check matters more than it sounds. `ffmpeg` seeking past the end of a
file with `-acodec copy` doesn't fail: it exits 0 and writes the tail of
the stream with negative timestamps. The clip looks perfectly valid, and
the model will happily hallucinate a clean, plausible sentence over it. A
wrong transcript is worse than no transcript, so an impossible range is a
hard error.

## Install

```sh
npx skills add zeke/transcription-skill
```

Requirements: Python 3, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (for
YouTube URLs), [`ffmpeg`](https://ffmpeg.org) (for video files and time
ranges), and a
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

## Transcription model

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
