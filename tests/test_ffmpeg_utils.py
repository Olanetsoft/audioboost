"""Tests for ffmpeg_utils: binary discovery, file probing, output parsing."""

import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

import ffmpeg_utils
from ffmpeg_utils import (
    FFmpegNotFoundError,
    FFprobeError,
    ProbeResult,
    _clamp_numeric,
    find_ffmpeg,
    find_ffprobe,
    parse_loudnorm_json,
    parse_progress_line,
    probe_file,
)


SAMPLE_LOUDNORM_OUTPUT = """
[Parsed_loudnorm_2 @ 0x1234567890]
{
    "input_i" : "-28.45",
    "input_tp" : "-12.34",
    "input_lra" : "7.20",
    "input_thresh" : "-38.67",
    "output_i" : "-14.02",
    "output_tp" : "-1.50",
    "output_lra" : "6.80",
    "output_thresh" : "-24.22",
    "normalization_type" : "dynamic",
    "target_offset" : "0.02"
}
"""


# ---------------------------------------------------------------------------
# find_ffmpeg / find_ffprobe
# ---------------------------------------------------------------------------


class FindFFmpegTest(unittest.TestCase):
    def test_path_hit_takes_precedence(self):
        with patch("ffmpeg_utils.shutil.which", return_value="/custom/ffmpeg"):
            self.assertEqual(find_ffmpeg(), "/custom/ffmpeg")

    def test_falls_back_to_apple_silicon_homebrew(self):
        with patch("ffmpeg_utils.shutil.which", return_value=None), \
             patch("ffmpeg_utils.os.path.isfile", side_effect=lambda p: p == "/opt/homebrew/bin/ffmpeg"), \
             patch("ffmpeg_utils.os.access", return_value=True):
            self.assertEqual(find_ffmpeg(), "/opt/homebrew/bin/ffmpeg")

    def test_falls_back_to_intel_homebrew(self):
        def isfile_side_effect(path):
            return path == "/usr/local/bin/ffmpeg"

        with patch("ffmpeg_utils.shutil.which", return_value=None), \
             patch("ffmpeg_utils.os.path.isfile", side_effect=isfile_side_effect), \
             patch("ffmpeg_utils.os.access", return_value=True):
            self.assertEqual(find_ffmpeg(), "/usr/local/bin/ffmpeg")

    def test_raises_when_nothing_found(self):
        with patch("ffmpeg_utils.shutil.which", return_value=None), \
             patch("ffmpeg_utils.os.path.isfile", return_value=False):
            with self.assertRaises(FFmpegNotFoundError):
                find_ffmpeg()

    def test_skips_candidate_without_exec_permission(self):
        with patch("ffmpeg_utils.shutil.which", return_value=None), \
             patch("ffmpeg_utils.os.path.isfile", return_value=True), \
             patch("ffmpeg_utils.os.access", return_value=False):
            with self.assertRaises(FFmpegNotFoundError):
                find_ffmpeg()


class FindFFprobeTest(unittest.TestCase):
    def test_prefers_sibling_of_ffmpeg(self):
        with patch("ffmpeg_utils.find_ffmpeg", return_value="/opt/homebrew/bin/ffmpeg"), \
             patch("ffmpeg_utils.os.path.isfile", side_effect=lambda p: p.endswith("/ffprobe")), \
             patch("ffmpeg_utils.os.access", return_value=True):
            self.assertEqual(find_ffprobe(), "/opt/homebrew/bin/ffprobe")

    def test_falls_back_to_path(self):
        with patch("ffmpeg_utils.find_ffmpeg", return_value="/opt/homebrew/bin/ffmpeg"), \
             patch("ffmpeg_utils.os.path.isfile", return_value=False), \
             patch("ffmpeg_utils.shutil.which", return_value="/somewhere/ffprobe"):
            self.assertEqual(find_ffprobe(), "/somewhere/ffprobe")

    def test_raises_when_nothing_found(self):
        with patch("ffmpeg_utils.find_ffmpeg", return_value="/opt/homebrew/bin/ffmpeg"), \
             patch("ffmpeg_utils.os.path.isfile", return_value=False), \
             patch("ffmpeg_utils.shutil.which", return_value=None):
            with self.assertRaises(FFmpegNotFoundError):
                find_ffprobe()

    def test_propagates_ffmpeg_not_found(self):
        with patch("ffmpeg_utils.find_ffmpeg", side_effect=FFmpegNotFoundError("nope")):
            with self.assertRaises(FFmpegNotFoundError):
                find_ffprobe()


# ---------------------------------------------------------------------------
# probe_file
# ---------------------------------------------------------------------------


def _fake_run(stdout: str, returncode: int = 0) -> MagicMock:
    """Return a CompletedProcess-like mock for subprocess.run."""
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


class ProbeFileTest(unittest.TestCase):
    def _patched_run(self, stdout: str):
        return patch("ffmpeg_utils.subprocess.run", return_value=_fake_run(stdout))

    def test_happy_path(self):
        payload = json.dumps({
            "format": {"duration": "12.5"},
            "streams": [
                {"codec_type": "video"},
                {"codec_type": "audio"},
            ],
        })
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             self._patched_run(payload):
            result = probe_file("/tmp/x.mp4")
        self.assertIsInstance(result, ProbeResult)
        self.assertAlmostEqual(result.duration_seconds, 12.5)
        self.assertTrue(result.has_audio)

    def test_video_without_audio_stream(self):
        payload = json.dumps({
            "format": {"duration": "3.0"},
            "streams": [{"codec_type": "video"}],
        })
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             self._patched_run(payload):
            result = probe_file("/tmp/silent.mp4")
        self.assertFalse(result.has_audio)
        self.assertAlmostEqual(result.duration_seconds, 3.0)

    def test_missing_format_defaults_duration_to_zero(self):
        payload = json.dumps({"streams": [{"codec_type": "audio"}]})
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             self._patched_run(payload):
            result = probe_file("/tmp/x.mp4")
        self.assertEqual(result.duration_seconds, 0.0)
        self.assertTrue(result.has_audio)

    def test_garbage_duration_coerces_to_zero(self):
        payload = json.dumps({
            "format": {"duration": "N/A"},
            "streams": [{"codec_type": "audio"}],
        })
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             self._patched_run(payload):
            result = probe_file("/tmp/x.mp4")
        self.assertEqual(result.duration_seconds, 0.0)

    def test_missing_streams_means_no_audio(self):
        payload = json.dumps({"format": {"duration": "1.0"}})
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             self._patched_run(payload):
            result = probe_file("/tmp/x.mp4")
        self.assertFalse(result.has_audio)

    def test_ffprobe_failure_raises_ffprobe_error(self):
        exc = subprocess.CalledProcessError(1, "ffprobe", stderr="boom")
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             patch("ffmpeg_utils.subprocess.run", side_effect=exc):
            with self.assertRaises(FFprobeError) as cm:
                probe_file("/tmp/missing.mp4")
            self.assertIn("boom", str(cm.exception))

    def test_ffprobe_timeout_raises_ffprobe_error(self):
        with patch("ffmpeg_utils.find_ffprobe", return_value="/bin/ffprobe"), \
             patch("ffmpeg_utils.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)):
            with self.assertRaises(FFprobeError):
                probe_file("/tmp/x.mp4")


# ---------------------------------------------------------------------------
# parse_loudnorm_json
# ---------------------------------------------------------------------------


class ParseLoudnormJsonTest(unittest.TestCase):
    def test_extracts_input_measurements(self):
        result = parse_loudnorm_json(SAMPLE_LOUDNORM_OUTPUT)
        self.assertEqual(result["input_i"], "-28.45")
        self.assertEqual(result["input_tp"], "-12.34")
        self.assertEqual(result["input_lra"], "7.20")
        self.assertEqual(result["input_thresh"], "-38.67")
        self.assertEqual(result["target_offset"], "0.02")

    def test_exposes_only_the_five_measurement_fields(self):
        result = parse_loudnorm_json(SAMPLE_LOUDNORM_OUTPUT)
        self.assertEqual(
            set(result.keys()),
            {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"},
        )

    def test_clamps_negative_infinity(self):
        stderr = (
            '{"input_i": "-inf", "input_tp": "-70.00", "input_lra": "0.00", '
            '"input_thresh": "-inf", "target_offset": "0.00"}'
        )
        result = parse_loudnorm_json(stderr)
        self.assertEqual(result["input_i"], "-70.00")
        self.assertEqual(result["input_thresh"], "-70.00")

    def test_clamps_positive_infinity_and_nan(self):
        stderr = (
            '{"input_i": "inf", "input_tp": "nan", "input_lra": "-nan", '
            '"input_thresh": "-14.00", "target_offset": "+inf"}'
        )
        result = parse_loudnorm_json(stderr)
        self.assertEqual(result["input_i"], "-70.00")
        self.assertEqual(result["input_tp"], "-70.00")
        self.assertEqual(result["input_lra"], "0.00")
        self.assertEqual(result["target_offset"], "0.00")

    def test_trailing_content_after_block_is_tolerated(self):
        noisy = SAMPLE_LOUDNORM_OUTPUT + "\n[some trailing ffmpeg log line]\n"
        result = parse_loudnorm_json(noisy)
        self.assertEqual(result["input_i"], "-28.45")

    def test_missing_block_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_loudnorm_json("no json block anywhere in this output")

    def test_missing_field_uses_numeric_fallback(self):
        # omit target_offset; parser substitutes a valid-float default.
        stderr = (
            '{"input_i": "-20.00", "input_tp": "-5.00", "input_lra": "7.00", '
            '"input_thresh": "-30.00"}'
        )
        result = parse_loudnorm_json(stderr)
        self.assertEqual(float(result["target_offset"]), 0.0)


# ---------------------------------------------------------------------------
# parse_progress_line
# ---------------------------------------------------------------------------


class ParseProgressLineTest(unittest.TestCase):
    def test_parses_key_value(self):
        self.assertEqual(
            parse_progress_line("out_time_ms=12345\n"),
            ("out_time_ms", "12345"),
        )

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(parse_progress_line("  key = value  "), ("key", "value"))

    def test_progress_end_marker(self):
        self.assertEqual(parse_progress_line("progress=end"), ("progress", "end"))

    def test_blank_line_returns_none(self):
        self.assertIsNone(parse_progress_line(""))
        self.assertIsNone(parse_progress_line("\n"))
        self.assertIsNone(parse_progress_line("   "))

    def test_line_without_equals_returns_none(self):
        self.assertIsNone(parse_progress_line("no equals here"))

    def test_equals_in_value_is_preserved(self):
        # partition uses the first '='; value keeps any additional equals.
        self.assertEqual(
            parse_progress_line("label=a=b=c"),
            ("label", "a=b=c"),
        )


# ---------------------------------------------------------------------------
# _clamp_numeric
# ---------------------------------------------------------------------------


class ClampNumericTest(unittest.TestCase):
    def test_passes_through_valid_float(self):
        self.assertEqual(_clamp_numeric("-14.03", -70.0), "-14.03")

    def test_passes_through_integer_looking_string(self):
        self.assertEqual(_clamp_numeric("7", 0.0), "7")

    def test_replaces_negative_inf(self):
        self.assertEqual(_clamp_numeric("-inf", -70.0), "-70.00")

    def test_replaces_positive_inf(self):
        self.assertEqual(_clamp_numeric("inf", 0.0), "0.00")

    def test_replaces_plus_inf(self):
        self.assertEqual(_clamp_numeric("+inf", 0.0), "0.00")

    def test_replaces_nan(self):
        self.assertEqual(_clamp_numeric("nan", 0.0), "0.00")

    def test_replaces_negative_nan(self):
        self.assertEqual(_clamp_numeric("-nan", 0.0), "0.00")

    def test_replaces_non_numeric_garbage(self):
        self.assertEqual(_clamp_numeric("oops", -1.5), "-1.50")

    def test_trims_surrounding_whitespace_for_check(self):
        self.assertEqual(_clamp_numeric("  -inf  ", -70.0), "-70.00")


if __name__ == "__main__":
    unittest.main()
