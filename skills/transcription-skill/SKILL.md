---
name: transcription-skill
description: >
  Transcribe a YouTube video or a local video/audio file to text. Use this
  skill whenever asked to transcribe a YouTube URL, get a transcript of a
  video or audio file, or turn spoken audio into text. Downloads YouTube
  videos with yt-dlp, extracts audio with ffmpeg, and transcribes with
  Google's gemini-3.5-flash on Replicate.
compatibility: Requires Python 3, yt-dlp (for YouTube URLs), ffmpeg (for video files), and a REPLICATE_API_TOKEN.
---

# Transcription skill

Transcribe a YouTube URL, a local video file, or a local audio file to plain
text using Google's `gemini-3.5-flash` on Replicate.

```sh
export REPLICATE_API_TOKEN=...
python3 <skill-directory>/scripts/transcribe.py <youtube-url | video-file | audio-file> [output-file]
```

Replace `<skill-directory>` with the directory containing this `SKILL.md`.

If the script exits saying `yt-dlp` or `ffmpeg` is missing, offer to install
it for the user (e.g. `brew install yt-dlp` or `brew install ffmpeg` on
macOS) before retrying, rather than just reporting the error.

## What it does, in order

1. If the input is a YouTube URL, downloads it with `yt-dlp` into the
   current directory under a slugified filename (lowercased title + video
   id, e.g. `my-video-title-abc123.mp4`).
2. If the input is a video file (or was just downloaded), extracts its
   audio with `ffmpeg` via stream copy (no re-encoding) and saves it
   alongside the video as `<slug>.m4a`.
3. Base64-encodes the audio and sends it to `google/gemini-3.5-flash` on
   Replicate with a verbatim-transcription prompt.
4. Polls until the prediction completes and writes the transcript to
   `<slug>.txt` (or the given output path).

An audio file input skips straight to step 3. `google/gemini-3.5-flash` is
hardcoded as the transcription model; see the root `README.md` for how
that choice was benchmarked against other models.

## Known gotchas

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
