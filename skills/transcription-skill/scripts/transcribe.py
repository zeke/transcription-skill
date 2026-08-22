#!/usr/bin/env python3
"""Transcribe a YouTube URL, video file, or audio file with Replicate's
google/gemini-3.5-flash.

Usage:
  transcribe.py <youtube-url | video-file | audio-file> [output-file]

- A YouTube URL is downloaded with yt-dlp and saved under a slugified
  filename (title + video id) in the current directory.
- A video file (or downloaded video) has its audio extracted with ffmpeg,
  saved alongside it as <slug>.m4a.
- An audio file is transcribed directly.

If [output-file] is omitted, the transcript is written next to the media
file with a .txt extension.

Requires:
  - REPLICATE_API_TOKEN in the environment
  - yt-dlp on PATH (only needed for YouTube URL input)
  - ffmpeg on PATH (only needed for video input)

This script has no dependencies beyond the Python standard library.
"""
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

MODEL = "google/gemini-3.5-flash"
API = "https://api.replicate.com/v1"

TRANSCRIBE_PROMPT = (
    "Transcribe this audio verbatim. Output only the plain text transcript, "
    "with no timestamps, speaker labels, or commentary."
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

# mimetypes.guess_type misidentifies some common audio extensions in ways
# Gemini's file sniffing rejects (e.g. .m4a -> audio/mp4a-latm). Prefer
# these known-good mappings first.
AUDIO_MIME_OVERRIDES = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
}


def token():
    t = os.environ.get("REPLICATE_API_TOKEN")
    if not t:
        sys.exit("REPLICATE_API_TOKEN is not set")
    return t


def api_request(method, path, body=None):
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
            # api.replicate.com blocks requests with no User-Agent.
            "User-Agent": "transcription-skill/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"Replicate API error ({e.code}): {detail}")


def is_url(value):
    return re.match(r"^https?://", value) is not None


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def download_video(url):
    """Download a YouTube video with yt-dlp under a slugified filename."""
    info = subprocess.run(
        ["yt-dlp", "--print", "%(title)s|||%(id)s", "--skip-download", url],
        capture_output=True,
        text=True,
    )
    if info.returncode != 0:
        sys.exit(f"yt-dlp failed to read video info:\n{info.stderr}")
    title, video_id = info.stdout.strip().split("|||")
    slug = slugify(f"{title}-{video_id}")
    dest = f"{slug}.mp4"

    print(f"downloading {url} -> {dest}...")
    result = subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bv*[ext=mp4]+ba[ext=m4a]/mp4",
            "-o",
            dest,
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(
            "yt-dlp failed to download the video (if this is a 403, try "
            f"`brew upgrade yt-dlp` and retry):\n{result.stderr}"
        )
    return dest


def extract_audio(video_path, audio_path=None):
    """Extract audio from a video via stream copy (no re-encoding)."""
    temp = audio_path is None
    if temp:
        fd, audio_path = tempfile.mkstemp(suffix=".m4a")
        os.close(fd)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "copy", audio_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if temp:
            os.unlink(audio_path)
        sys.exit(f"ffmpeg failed to extract audio:\n{result.stderr}")
    return audio_path, temp


def guess_mime(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in AUDIO_MIME_OVERRIDES:
        return AUDIO_MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(path)
    return mime or "audio/mp4"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    source = sys.argv[1]

    if is_url(source):
        media_path = download_video(source)
    else:
        if not os.path.isfile(source):
            sys.exit(f"No such file: {source}")
        media_path = source

    ext = os.path.splitext(media_path)[1].lower()
    output_path = (
        sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(media_path)[0] + ".txt"
    )

    audio_path = media_path
    cleanup_audio = False
    if ext in VIDEO_EXTENSIONS:
        # Save the extracted audio alongside the video (e.g. slug.mp4 ->
        # slug.m4a) rather than a throwaway temp file, since it's a useful
        # artifact on its own.
        sibling_audio = os.path.splitext(media_path)[0] + ".m4a"
        print(f"extracting audio from {media_path} -> {sibling_audio}...")
        audio_path, cleanup_audio = extract_audio(media_path, sibling_audio)

    try:
        print(f"resolving latest version of {MODEL}...")
        model = api_request("GET", f"/models/{MODEL}")
        version_id = model["latest_version"]["id"]

        with open(audio_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        data_uri = f"data:{guess_mime(audio_path)};base64,{b64}"

        print(f"submitting prediction (version {version_id[:12]}...)")
        started = time.time()
        pred = api_request(
            "POST",
            "/predictions",
            {
                "version": version_id,
                "input": {"audio": data_uri, "prompt": TRANSCRIBE_PROMPT},
            },
        )
        pred_id = pred["id"]

        while pred["status"] not in ("succeeded", "failed", "canceled"):
            time.sleep(5)
            pred = api_request("GET", f"/predictions/{pred_id}")
            print(f"status: {pred['status']}")

        if pred["status"] != "succeeded":
            sys.exit(f"prediction failed: {pred.get('error')}")

        output = pred["output"]
        text = "".join(output) if isinstance(output, list) else output

        with open(output_path, "w") as f:
            f.write(text)

        elapsed = round(time.time() - started, 1)
        print(f"saved {output_path} ({len(text.split())} words, {elapsed}s)")
    finally:
        if cleanup_audio:
            os.unlink(audio_path)


if __name__ == "__main__":
    main()
