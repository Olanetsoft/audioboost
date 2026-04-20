"""Tests for pure parsing helpers in ffmpeg_utils."""

import unittest

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

from ffmpeg_utils import (
    _clamp_numeric,
    parse_loudnorm_json,
    parse_progress_line,
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


class ParseLoudnormJsonTest(unittest.TestCase):
    def test_extracts_input_measurements(self):
        result = parse_loudnorm_json(SAMPLE_LOUDNORM_OUTPUT)
        self.assertEqual(result["input_i"], "-28.45")
        self.assertEqual(result["input_tp"], "-12.34")
        self.assertEqual(result["input_lra"], "7.20")
        self.assertEqual(result["input_thresh"], "-38.67")
        self.assertEqual(result["target_offset"], "0.02")

    def test_clamps_negative_infinity(self):
        stderr = (
            '{"input_i": "-inf", "input_tp": "-70.00", "input_lra": "0.00", '
            '"input_thresh": "-inf", "target_offset": "0.00"}'
        )
        result = parse_loudnorm_json(stderr)
        self.assertEqual(result["input_i"], "-70.00")
        self.assertEqual(result["input_thresh"], "-70.00")

    def test_missing_block_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_loudnorm_json("no json block anywhere in this output")


class ParseProgressLineTest(unittest.TestCase):
    def test_parses_key_value(self):
        self.assertEqual(
            parse_progress_line("out_time_ms=12345\n"),
            ("out_time_ms", "12345"),
        )

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(parse_progress_line("  key = value  "), ("key", "value"))

    def test_blank_line_returns_none(self):
        self.assertIsNone(parse_progress_line(""))
        self.assertIsNone(parse_progress_line("\n"))
        self.assertIsNone(parse_progress_line("   "))

    def test_line_without_equals_returns_none(self):
        self.assertIsNone(parse_progress_line("no equals here"))


class ClampNumericTest(unittest.TestCase):
    def test_passes_through_valid_float(self):
        self.assertEqual(_clamp_numeric("-14.03", -70.0), "-14.03")

    def test_replaces_negative_inf(self):
        self.assertEqual(_clamp_numeric("-inf", -70.0), "-70.00")

    def test_replaces_positive_inf(self):
        self.assertEqual(_clamp_numeric("inf", 0.0), "0.00")

    def test_replaces_nan(self):
        self.assertEqual(_clamp_numeric("nan", 0.0), "0.00")

    def test_replaces_non_numeric_garbage(self):
        self.assertEqual(_clamp_numeric("oops", -1.5), "-1.50")


if __name__ == "__main__":
    unittest.main()
