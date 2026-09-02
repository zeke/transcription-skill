---
name: transcription-skill
description: >
  Transcribe a YouTube video or a local video/audio file to text. Use this
  skill whenever asked to transcribe a YouTube URL, get a transcript of a
  video or audio file, or turn spoken audio into text. Also use it to
  transcribe only part of a video or audio file, such as a clip, an excerpt,
  or a time range like "from 15:08 to 16:22", in which case only that range
  is downloaded. Downloads YouTube videos with yt-dlp, extracts and trims
  audio with ffmpeg, and transcribes with Google's gemini-3.5-flash on
  Replicate.
compatibility: Requires Python 3, yt-dlp (for YouTube URLs), ffmpeg (for video files and time ranges), and a REPLICATE_API_TOKEN.
---

# Transcription skill

Transcribe a YouTube URL, a local video file, or a local audio file to plain
text using Google's `gemini-3.5-flash` on Replicate.

```sh
export REPLICATE_API_TOKEN=...
python3 <skill-directory>/scripts/transcribe.py <youtube-url | video-file | audio-file> [output-file] [--from TIME] [--to TIME]
```

Replace `<skill-directory>` with the directory containing this `SKILL.md`.

If the script exits saying `yt-dlp` or `ffmpeg` is missing, offer to install
it for the user (e.g. `brew install yt-dlp` or `brew install ffmpeg` on
macOS) before retrying, rather than just reporting the error.

## Transcribing part of a video

When the user names a time range, pass it through with `--from` and `--to`
rather than transcribing the whole thing. Times can be `SS`, `MM:SS`, or
`HH:MM:SS`, and either flag can be used alone.

```sh
python3 <skill-directory>/scripts/transcribe.py "https://youtu.be/abc123" --from 15:08 --to 16:22
```

For a YouTube URL this passes `--download-sections` to `yt-dlp`, so only
the requested range crosses the network. On a 108-minute podcast, pulling
a 74-second clip moves about 23 MB instead of the full download, and the
prediction sees 74 seconds of audio instead of an hour and a half.

Clipped files carry the range in their names (e.g.
`<slug>-15m08s-16m22s.m4a`), so clips never overwrite a full-length
transcript of the same video. Trimming a local file needs `ffmpeg` even
when the input is already audio.

A range that starts past the end of the media is rejected before anything
is downloaded or cut. A range that merely ends past it warns and
transcribes up to the end.

## What it does, in order

1. If the input is a YouTube URL, downloads it with `yt-dlp` into the
   current directory under a slugified filename (lowercased title + video
   id, e.g. `my-video-title-abc123.mp4`), fetching only the `--from`/`--to`
   range if one was given.
2. If the input is a video file (or was just downloaded), extracts its
   audio with `ffmpeg` via stream copy (no re-encoding) and saves it
   alongside the video as `<slug>.m4a`. A local audio input with a time
   range is trimmed the same way.
3. Base64-encodes the audio and sends it to `google/gemini-3.5-flash` on
   Replicate with a verbatim-transcription prompt.
4. Polls until the prediction completes and writes the transcript to
   `<slug>.txt` (or the given output path).

An audio file input skips straight to step 3. `google/gemini-3.5-flash` is
hardcoded as the transcription model; see the root `README.md` for how
that choice was benchmarked against other models.

## Known gotchas

- **ffmpeg seeking past the end of a file doesn't fail.** With `-ss` beyond
  the media's duration and `-acodec copy`, ffmpeg exits 0 and writes the
  tail of the stream with negative timestamps (`time=-02:59:00.00`) instead
  of an empty file. Gemini then hallucinates a plausible sentence over that
  garbage. This is why the requested range is checked against the source
  duration up front rather than by inspecting the resulting clip.

- **YouTube 403s.** `yt-dlp`'s extractor breaks against YouTube frequently.
  If downloads fail with `HTTP Error 403: Forbidden`, run
  `brew upgrade yt-dlp` (or update however it was installed) and retry.
- **Gemini can't fetch Replicate's own file URLs.** Uploading audio to
  Replicate's `/v1/files` and passing that URL as the `audio` input fails
  because Gemini's backend can't authenticate the fetch, and gets back a
  401 JSON response it reports as "could not determine mimetype". Send the
  audio as a base64 `data:` URI directly in the prediction input instead.
- **`.m4a` mimetype sniffing.** Python's `mimetypes.guess_type` reports
  `.m4a` as `audio/mp4a-latm`, which Gemini rejects. Use `audio/mp4`.
- **`api.replicate.com` blocks requests with no `User-Agent` header**
  (Cloudflare error 1010). Always set one.
- **Pin to the model's current `latest_version`.** Don't hardcode a
  version id — Google ships new Gemini versions on Replicate often enough
  that hardcoded ids go stale.
