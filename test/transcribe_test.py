import importlib.util
import os
import unittest

SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "skills",
    "transcription-skill",
    "scripts",
    "transcribe.py",
)

spec = importlib.util.spec_from_file_location("transcribe", SCRIPT_PATH)
transcribe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcribe)


class IsUrlTest(unittest.TestCase):
    def test_http_and_https_urls(self):
        self.assertTrue(transcribe.is_url("https://www.youtube.com/watch?v=abc123"))
        self.assertTrue(transcribe.is_url("http://youtu.be/abc123"))

    def test_local_paths_are_not_urls(self):
        self.assertFalse(transcribe.is_url("video.mp4"))
        self.assertFalse(transcribe.is_url("/tmp/video.mp4"))
        self.assertFalse(transcribe.is_url("./relative/audio.m4a"))


class SlugifyTest(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(
            transcribe.slugify("I Built an AI Agent to Cure AI Slop-gO6eRAhzjss"),
            "i-built-an-ai-agent-to-cure-ai-slop-go6erahzjss",
        )

    def test_strips_leading_trailing_punctuation(self):
        self.assertEqual(transcribe.slugify("  Hello, World!  "), "hello-world")

    def test_collapses_repeated_separators(self):
        self.assertEqual(transcribe.slugify("a---b   c"), "a-b-c")


class RequireToolTest(unittest.TestCase):
    def test_passes_when_tool_present(self):
        try:
            transcribe.require_tool("python3", "run tests")
        except SystemExit:
            self.fail("require_tool raised SystemExit for a tool that exists")

    def test_exits_with_install_hint_when_missing(self):
        with self.assertRaises(SystemExit) as ctx:
            transcribe.require_tool("definitely-not-a-real-tool", "do a thing")
        message = str(ctx.exception)
        self.assertIn("definitely-not-a-real-tool", message)
        self.assertIn("brew install", message)


class ParseTimestampTest(unittest.TestCase):
    def test_accepted_formats(self):
        self.assertEqual(transcribe.parse_timestamp("90"), 90)
        self.assertEqual(transcribe.parse_timestamp("15:08"), 908)
        self.assertEqual(transcribe.parse_timestamp("1:02:03"), 3723)
        self.assertEqual(transcribe.parse_timestamp(" 0:01.5 "), 1.5)

    def test_rejects_garbage(self):
        for value in ("abc", "1:2:3:4", "", "12:", "-5"):
            with self.assertRaises(ValueError):
                transcribe.parse_timestamp(value)


class ClipSuffixTest(unittest.TestCase):
    def test_empty_without_a_range(self):
        self.assertEqual(transcribe.clip_suffix(None, None), "")

    def test_start_and_end(self):
        self.assertEqual(transcribe.clip_suffix(908, 982), "-15m08s-16m22s")

    def test_open_ended_range(self):
        self.assertEqual(transcribe.clip_suffix(908, None), "-15m08s-end")

    def test_start_defaults_to_zero(self):
        self.assertEqual(transcribe.clip_suffix(None, 982), "-0m00s-16m22s")

    def test_includes_hours_past_an_hour(self):
        self.assertEqual(transcribe.clip_suffix(3723, 3800), "-1h02m03s-1h03m20s")


class TrimArgsTest(unittest.TestCase):
    def test_expresses_the_range_as_a_duration(self):
        self.assertEqual(
            transcribe.trim_args(908, 982), (["-ss", "908"], ["-t", "74"])
        )

    def test_open_start_and_open_end(self):
        self.assertEqual(transcribe.trim_args(None, 982), ([], ["-t", "982"]))
        self.assertEqual(transcribe.trim_args(908, None), (["-ss", "908"], []))

    def test_no_flags_without_a_range(self):
        self.assertEqual(transcribe.trim_args(None, None), ([], []))


class ParseArgsTest(unittest.TestCase):
    def test_source_only(self):
        args = transcribe.parse_args(["video.mp4"])
        self.assertEqual(args.source, "video.mp4")
        self.assertIsNone(args.output)
        self.assertIsNone(args.start)
        self.assertIsNone(args.end)

    def test_output_and_range(self):
        args = transcribe.parse_args(
            ["video.mp4", "out.txt", "--from", "15:08", "--to", "16:22"]
        )
        self.assertEqual(args.output, "out.txt")
        self.assertEqual((args.start, args.end), (908, 982))

    def test_rejects_backwards_range(self):
        with self.assertRaises(SystemExit):
            transcribe.parse_args(["video.mp4", "--from", "2:00", "--to", "1:00"])

    def test_rejects_invalid_timestamp(self):
        with self.assertRaises(SystemExit):
            transcribe.parse_args(["video.mp4", "--from", "banana"])


class ProbeDurationTest(unittest.TestCase):
    def test_returns_none_for_unreadable_media(self):
        self.assertIsNone(transcribe.probe_duration("/nonexistent/file.m4a"))


class RangeProblemsTest(unittest.TestCase):
    def test_range_inside_the_media_is_fine(self):
        self.assertEqual(transcribe.range_problems(6460, 908, 982), (None, None))

    def test_unknown_duration_is_not_second_guessed(self):
        self.assertEqual(transcribe.range_problems(None, 908, 982), (None, None))

    def test_start_past_the_end_is_an_error(self):
        error, warning = transcribe.range_problems(60, 10800, 10830)
        self.assertIn("3h00m00s", error)
        self.assertIn("1m00s", error)
        self.assertIsNone(warning)

    def test_start_exactly_at_the_end_is_an_error(self):
        error, _ = transcribe.range_problems(60, 60, None)
        self.assertIsNotNone(error)

    def test_end_past_the_end_only_warns(self):
        error, warning = transcribe.range_problems(60, 30, 90)
        self.assertIsNone(error)
        self.assertIn("1m30s", warning)


class GuessMimeTest(unittest.TestCase):
    def test_m4a_override(self):
        self.assertEqual(transcribe.guess_mime("audio.m4a"), "audio/mp4")

    def test_mp3_override(self):
        self.assertEqual(transcribe.guess_mime("audio.mp3"), "audio/mpeg")

    def test_falls_back_to_mimetypes_module(self):
        self.assertEqual(transcribe.guess_mime("audio.wav"), "audio/wav")


if __name__ == "__main__":
    unittest.main()
