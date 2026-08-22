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


class GuessMimeTest(unittest.TestCase):
    def test_m4a_override(self):
        self.assertEqual(transcribe.guess_mime("audio.m4a"), "audio/mp4")

    def test_mp3_override(self):
        self.assertEqual(transcribe.guess_mime("audio.mp3"), "audio/mpeg")

    def test_falls_back_to_mimetypes_module(self):
        self.assertEqual(transcribe.guess_mime("audio.wav"), "audio/wav")


if __name__ == "__main__":
    unittest.main()
