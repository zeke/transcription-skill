#!/usr/bin/env python3
"""Transcribe a YouTube URL, video file, or audio file with Replicate's
google/gemini-3.5-flash.

Usage:
  transcribe.py <youtube-url | video-file | audio-file> [output-file]
                [--from TIME] [--to TIME]

- A YouTube URL is downloaded with yt-dlp and saved under a slugified
  filename (title + video id) in the current directory.
- A video file (or downloaded video) has its audio extracted with ffmpeg,
  saved alongside it as <slug>.m4a.
- An audio file is transcribed directly.

--from/--to transcribe only a time range, given as SS, MM:SS, or
HH:MM:SS. For a YouTube URL only that range is downloaded, so long
videos cost a fraction of the bandwidth and prediction time. Clipped
files get a suffix (e.g. <slug>-15m08s-16m22s.m4a) so they don't
overwrite full-length ones.

If [output-file] is omitted, the transcript is written next to the media
file with a .txt extension.

Requires:
  - REPLICATE_API_TOKEN in the environment
  - yt-dlp on PATH (only needed for YouTube URL input)
  - ffmpeg on PATH (needed for video input, and for any --from/--to
    trimming of local files)

This script has no dependencies beyond the Python standard library.
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
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


def require_tool(tool, purpose):
    if shutil.which(tool) is None:
        sys.exit(
            f"'{tool}' is required to {purpose} but wasn't found on PATH. "
            f"Install it (e.g. `brew install {tool}`) and try again."
        )


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


def parse_timestamp(value):
    """Parse SS, MM:SS, or HH:MM:SS into seconds."""
    parts = value.strip().split(":")
    if len(parts) > 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(
            f"invalid timestamp {value!r}; use SS, MM:SS, or HH:MM:SS"
        )
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def seconds_str(seconds):
    """Render seconds for a CLI argument, dropping a pointless ".0"."""
    return str(int(seconds)) if float(seconds).is_integer() else str(seconds)


def format_timestamp(seconds):
    """Render seconds as a filename-safe label, e.g. 908 -> 15m08s."""
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"


def clip_suffix(start, end):
    """Filename suffix marking the clipped range, or "" if untrimmed."""
    if start is None and end is None:
        return ""
    return "-" + "-".join(
        format_timestamp(t) if t is not None else "end"
        for t in (start if start is not None else 0, end)
    )


def download_video(url, start=None, end=None):
    """Download a YouTube video with yt-dlp under a slugified filename."""
    require_tool("yt-dlp", "download YouTube videos")
    info = subprocess.run(
        [
            "yt-dlp",
            "--print",
            "%(title)s|||%(id)s|||%(duration)s",
            "--skip-download",
            url,
        ],
        capture_output=True,
        text=True,
    )
    if info.returncode != 0:
        sys.exit(f"yt-dlp failed to read video info:\n{info.stderr}")
    title, video_id, duration = info.stdout.strip().split("|||")
    # Validate before downloading, so an impossible range costs nothing.
    try:
        check_range(float(duration), start, end)
    except ValueError:
        pass  # live streams and some videos report no duration
    slug = slugify(f"{title}-{video_id}")
    dest = f"{slug}{clip_suffix(start, end)}.mp4"

    command = ["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/mp4", "-o", dest]
    if start is not None or end is not None:
        # yt-dlp cuts the requested range out server-side, so only the clip
        # is transferred instead of the whole video.
        section = (
            f"*{seconds_str(start or 0)}-"
            f"{seconds_str(end) if end is not None else 'inf'}"
        )
        command += ["--download-sections", section, "--force-keyframes-at-cuts"]
        require_tool("ffmpeg", "download a section of a YouTube video")

    print(f"downloading {url} -> {dest}...")
    result = subprocess.run(
        command + [url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(
            "yt-dlp failed to download the video (if this is a 403, try "
            f"`brew upgrade yt-dlp` and retry):\n{result.stderr}"
        )
    return dest


def trim_args(start, end):
    """ffmpeg input/output flags for a time range.

    -ss goes before -i for a fast seek; the range length is expressed as -t
    rather than -to, which would otherwise be measured from the seek point.
    """
    before = ["-ss", seconds_str(start)] if start is not None else []
    after = ["-t", seconds_str(end - (start or 0))] if end is not None else []
    return before, after


def extract_audio(video_path, audio_path=None, start=None, end=None):
    """Extract audio from a video via stream copy (no re-encoding)."""
    require_tool("ffmpeg", "extract audio from video files")
    temp = audio_path is None
    if temp:
        fd, audio_path = tempfile.mkstemp(suffix=".m4a")
        os.close(fd)
    before, after = trim_args(start, end)
    result = subprocess.run(
        ["ffmpeg", "-y"]
        + before
        + ["-i", video_path, "-vn", "-acodec", "copy"]
        + after
        + [audio_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if temp:
            os.unlink(audio_path)
        sys.exit(f"ffmpeg failed to extract audio:\n{result.stderr}")
    return audio_path, temp


def trim_audio(audio_path, start, end):
    """Copy a time range of an audio file into a sibling clip file."""
    require_tool("ffmpeg", "trim audio files")
    base, ext = os.path.splitext(audio_path)
    clip_path = f"{base}{clip_suffix(start, end)}{ext}"
    before, after = trim_args(start, end)
    print(f"trimming {audio_path} -> {clip_path}...")
    result = subprocess.run(
        ["ffmpeg", "-y"] + before + ["-i", audio_path, "-c", "copy"] + after + [clip_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed to trim audio:\n{result.stderr}")
    return clip_path


def probe_duration(path):
    """Duration of a media file in seconds, or None if it can't be read.

    ffprobe ships with ffmpeg, but this returns None rather than exiting
    when it's unavailable, so a missing ffprobe can't block a transcript.
    """
    if shutil.which("ffprobe") is None:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def range_problems(duration, start, end):
    """Check a requested range against a known media duration.

    Returns (error, warning), either of which may be None. A start past the
    end of the media is fatal: ffmpeg seeking past EOF under stream copy
    doesn't fail, it emits the tail of the stream with negative timestamps,
    which transcribes as plausible-looking nonsense.
    """
    if duration is None:
        return None, None
    label = format_timestamp(duration)
    if start is not None and start >= duration:
        return (
            f"--from {format_timestamp(start)} starts at or after the end of "
            f"the media, which is only {label} long."
        ), None
    if end is not None and end > duration:
        return None, (
            f"--to {format_timestamp(end)} is past the end of the media "
            f"({label}); transcribing up to the end instead."
        )
    return None, None


def check_range(duration, start, end):
    """Exit on an impossible range, warn on one that overshoots the end."""
    error, warning = range_problems(duration, start, end)
    if error:
        sys.exit(error)
    if warning:
        print(f"warning: {warning}")


def guess_mime(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in AUDIO_MIME_OVERRIDES:
        return AUDIO_MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(path)
    return mime or "audio/mp4"


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Transcribe a YouTube URL, video file, or audio file."
    )
    parser.add_argument("source", help="YouTube URL, video file, or audio file")
    parser.add_argument(
        "output", nargs="?", help="transcript path (default: alongside the media file)"
    )
    parser.add_argument(
        "--from",
        dest="start",
        metavar="TIME",
        help="start of the range to transcribe (SS, MM:SS, or HH:MM:SS)",
    )
    parser.add_argument(
        "--to",
        dest="end",
        metavar="TIME",
        help="end of the range to transcribe (SS, MM:SS, or HH:MM:SS)",
    )
    args = parser.parse_args(argv)

    for name in ("start", "end"):
        value = getattr(args, name)
        if value is not None:
            try:
                setattr(args, name, parse_timestamp(value))
            except ValueError as e:
                parser.error(str(e))
    if args.start is not None and args.end is not None and args.end <= args.start:
        parser.error("--to must be later than --from")
    return args


def main():
    args = parse_args(sys.argv[1:])
    source = args.source
    start, end = args.start, args.end

    trimmed = False
    if is_url(source):
        media_path = download_video(source, start, end)
        trimmed = True
    else:
        if not os.path.isfile(source):
            sys.exit(f"No such file: {source}")
        media_path = source

    ext = os.path.splitext(media_path)[1].lower()

    audio_path = media_path
    cleanup_audio = False
    if ext in VIDEO_EXTENSIONS:
        # Save the extracted audio alongside the video (e.g. slug.mp4 ->
        # slug.m4a) rather than a throwaway temp file, since it's a useful
        # artifact on its own.
        if not trimmed:
            check_range(probe_duration(media_path), start, end)
        suffix = "" if trimmed else clip_suffix(start, end)
        sibling_audio = os.path.splitext(media_path)[0] + suffix + ".m4a"
        print(f"extracting audio from {media_path} -> {sibling_audio}...")
        audio_path, cleanup_audio = extract_audio(
            media_path,
            sibling_audio,
            None if trimmed else start,
            None if trimmed else end,
        )
    elif not trimmed and (start is not None or end is not None):
        check_range(probe_duration(audio_path), start, end)
        audio_path = trim_audio(audio_path, start, end)

    output_path = args.output or os.path.splitext(audio_path)[0] + ".txt"

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
