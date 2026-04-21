"""Tests for the Tk-free helpers in gui_helpers."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

import gui_helpers
from gui_helpers import (
    Palette,
    QueueItem,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    format_queue_header,
    human_size,
    is_dark_mode,
    parse_dnd_paths,
    summarize_completion,
)


# ---------------------------------------------------------------------------
# human_size
# ---------------------------------------------------------------------------


class HumanSizeTest(unittest.TestCase):
    def test_zero_bytes(self):
        self.assertEqual(human_size(0), "0 B")

    def test_small_bytes(self):
        self.assertEqual(human_size(1023), "1023 B")

    def test_one_kilobyte(self):
        self.assertEqual(human_size(1024), "1.0 KB")

    def test_one_point_five_kilobytes(self):
        self.assertEqual(human_size(1536), "1.5 KB")

    def test_megabyte_scale(self):
        self.assertEqual(human_size(1024 * 1024), "1.0 MB")

    def test_gigabyte_scale(self):
        self.assertEqual(human_size(1024 ** 3), "1.0 GB")

    def test_very_large_falls_back_to_tb(self):
        # 10 PB still formats in TB (no PB unit by design).
        self.assertTrue(human_size(10 * (1024 ** 5)).endswith(" TB"))

    def test_bytes_never_show_decimal(self):
        self.assertEqual(human_size(42), "42 B")

    def test_414_mb_example(self):
        # Matches the filename display AudioBoost shows for a ~414 MB file.
        formatted = human_size(414 * 1024 * 1024)
        self.assertEqual(formatted, "414.0 MB")


# ---------------------------------------------------------------------------
# parse_dnd_paths
# ---------------------------------------------------------------------------


class ParseDndPathsTest(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(parse_dnd_paths(""), [])

    def test_single_path(self):
        self.assertEqual(parse_dnd_paths("/tmp/a.mp4"), ["/tmp/a.mp4"])

    def test_two_simple_paths(self):
        self.assertEqual(
            parse_dnd_paths("/tmp/a.mp4 /tmp/b.mp4"),
            ["/tmp/a.mp4", "/tmp/b.mp4"],
        )

    def test_braced_path_with_spaces(self):
        self.assertEqual(
            parse_dnd_paths("{/tmp/my clip.mp4}"),
            ["/tmp/my clip.mp4"],
        )

    def test_mixed_plain_and_braced(self):
        self.assertEqual(
            parse_dnd_paths("/tmp/a.mp4 {/tmp/b c.mp4} /tmp/d.mp4"),
            ["/tmp/a.mp4", "/tmp/b c.mp4", "/tmp/d.mp4"],
        )

    def test_multiple_spaces_are_collapsed(self):
        self.assertEqual(
            parse_dnd_paths("/tmp/a.mp4   /tmp/b.mp4"),
            ["/tmp/a.mp4", "/tmp/b.mp4"],
        )

    def test_leading_and_trailing_whitespace(self):
        self.assertEqual(
            parse_dnd_paths(" /tmp/a.mp4 "),
            ["/tmp/a.mp4"],
        )

    def test_braced_path_with_special_chars(self):
        self.assertEqual(
            parse_dnd_paths("{/tmp/weird & (file).mp4}"),
            ["/tmp/weird & (file).mp4"],
        )


# ---------------------------------------------------------------------------
# is_dark_mode
# ---------------------------------------------------------------------------


def _defaults_result(*, stdout: str, returncode: int) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


class IsDarkModeTest(unittest.TestCase):
    def test_returns_true_when_defaults_prints_dark(self):
        with patch("gui_helpers.subprocess.run",
                   return_value=_defaults_result(stdout="Dark\n", returncode=0)):
            self.assertTrue(is_dark_mode())

    def test_returns_false_when_defaults_exits_nonzero(self):
        # Light mode: the AppleInterfaceStyle key isn't set, so defaults fails.
        with patch("gui_helpers.subprocess.run",
                   return_value=_defaults_result(stdout="", returncode=1)):
            self.assertFalse(is_dark_mode())

    def test_returns_false_for_unexpected_output(self):
        with patch("gui_helpers.subprocess.run",
                   return_value=_defaults_result(stdout="Aubergine\n", returncode=0)):
            self.assertFalse(is_dark_mode())

    def test_returns_false_on_timeout(self):
        with patch("gui_helpers.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="defaults", timeout=1)):
            self.assertFalse(is_dark_mode())

    def test_returns_false_on_oserror(self):
        with patch("gui_helpers.subprocess.run", side_effect=OSError("no binary")):
            self.assertFalse(is_dark_mode())

    def test_strips_trailing_whitespace(self):
        with patch("gui_helpers.subprocess.run",
                   return_value=_defaults_result(stdout="  Dark  \n", returncode=0)):
            self.assertTrue(is_dark_mode())


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------


class PaletteTest(unittest.TestCase):
    def test_dark_palette_has_all_required_attrs(self):
        p = Palette(dark=True)
        for attr in Palette._REQUIRED_ATTRS:
            self.assertTrue(hasattr(p, attr), f"missing {attr} on dark palette")

    def test_light_palette_has_all_required_attrs(self):
        p = Palette(dark=False)
        for attr in Palette._REQUIRED_ATTRS:
            self.assertTrue(hasattr(p, attr), f"missing {attr} on light palette")

    def test_dark_flag_is_preserved(self):
        self.assertTrue(Palette(dark=True).dark)
        self.assertFalse(Palette(dark=False).dark)

    def test_accent_differs_between_modes(self):
        # Dark mode uses a lighter indigo so it's readable on dark bg.
        self.assertNotEqual(Palette(dark=True).accent, Palette(dark=False).accent)

    def test_drop_bg_differs_between_modes(self):
        self.assertNotEqual(Palette(dark=True).drop_bg, Palette(dark=False).drop_bg)

    def test_all_colors_are_hex_strings(self):
        for dark in (True, False):
            p = Palette(dark=dark)
            for attr in Palette._REQUIRED_ATTRS:
                value = getattr(p, attr)
                self.assertIsInstance(value, str,
                                      f"{attr} in {'dark' if dark else 'light'} palette")
                self.assertRegex(value, r"^#[0-9a-fA-F]{6}$",
                                 f"{attr} in {'dark' if dark else 'light'} palette")

    def test_accent_fg_is_white(self):
        # Text on the accent pill must stay readable in both modes.
        self.assertEqual(Palette(dark=True).accent_fg, "#ffffff")
        self.assertEqual(Palette(dark=False).accent_fg, "#ffffff")

    def test_segment_track_contrasts_with_segment_bg(self):
        # Pills float above a different-shaded track; same color would erase
        # the raised-pill effect that the UI relies on.
        for dark in (True, False):
            p = Palette(dark=dark)
            self.assertNotEqual(p.segment_track, p.segment_bg)


# ---------------------------------------------------------------------------
# QueueItem / batch helpers
# ---------------------------------------------------------------------------


def _item(path: str, size: int = 1024, status: str = STATUS_PENDING) -> QueueItem:
    return QueueItem(path=path, size_bytes=size, status=status)


class QueueItemTest(unittest.TestCase):
    def test_basename_strips_directory(self):
        self.assertEqual(_item("/tmp/sub/clip.mp4").basename, "clip.mp4")

    def test_display_row_includes_status_icon(self):
        row = _item("/tmp/clip.mp4", size=2048).display_row()
        self.assertIn("clip.mp4", row)
        self.assertIn("○", row)  # pending

    def test_display_row_reflects_status_transitions(self):
        icons = {
            STATUS_PENDING: "○",
            STATUS_PROCESSING: "◐",
            STATUS_DONE: "✓",
            STATUS_FAILED: "✗",
        }
        for status, icon in icons.items():
            row = _item("/tmp/x.mp4", status=status).display_row()
            self.assertIn(icon, row, status)

    def test_display_row_includes_size(self):
        row = _item("/tmp/x.mp4", size=1024 * 1024).display_row()
        self.assertIn("1.0 MB", row)


class FormatQueueHeaderTest(unittest.TestCase):
    def test_empty_queue_returns_empty_string(self):
        self.assertEqual(format_queue_header([]), "")

    def test_single_file_pluralization(self):
        self.assertEqual(
            format_queue_header([_item("/tmp/a.mp4")]),
            "1 file queued",
        )

    def test_multiple_files_pluralization(self):
        items = [_item(f"/tmp/{i}.mp4") for i in range(3)]
        self.assertEqual(format_queue_header(items), "3 files queued")

    def test_processing_label_shows_position_and_filename(self):
        items = [_item("/tmp/a.mp4"), _item("/tmp/b.mp4"), _item("/tmp/c.mp4")]
        self.assertEqual(
            format_queue_header(items, processing_index=1),
            "Processing 2 of 3  ·  b.mp4",
        )

    def test_processing_index_out_of_range_returns_empty(self):
        items = [_item("/tmp/a.mp4")]
        self.assertEqual(format_queue_header(items, processing_index=5), "")


class SummarizeCompletionTest(unittest.TestCase):
    def test_all_saved_singular(self):
        self.assertEqual(
            summarize_completion([_item("/tmp/a.mp4", status=STATUS_DONE)]),
            "✓ Saved 1 file",
        )

    def test_all_saved_plural(self):
        items = [_item(f"/tmp/{i}.mp4", status=STATUS_DONE) for i in range(3)]
        self.assertEqual(summarize_completion(items), "✓ Saved 3 files")

    def test_all_failed(self):
        items = [
            _item("/tmp/a.mp4", status=STATUS_FAILED),
            _item("/tmp/b.mp4", status=STATUS_FAILED),
        ]
        self.assertEqual(summarize_completion(items), "Failed: 2 files")

    def test_mixed_outcome(self):
        items = [
            _item("/tmp/a.mp4", status=STATUS_DONE),
            _item("/tmp/b.mp4", status=STATUS_DONE),
            _item("/tmp/c.mp4", status=STATUS_FAILED),
        ]
        self.assertEqual(summarize_completion(items), "Done: 2 saved · 1 failed")


if __name__ == "__main__":
    unittest.main()
