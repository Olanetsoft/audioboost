"""Tests for the toolkit-free helpers in gui_helpers."""

import os
import tempfile
import unittest

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

from gui_helpers import (
    QueueItem,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    human_size,
    load_settings,
    save_settings,
    settings_path,
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
        self.assertTrue(human_size(10 * (1024 ** 5)).endswith(" TB"))

    def test_bytes_never_show_decimal(self):
        self.assertEqual(human_size(42), "42 B")


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "nested", "settings.json")

    def test_default_path_is_application_support(self):
        self.assertTrue(
            settings_path().endswith(
                "Library/Application Support/AudioBoost/settings.json"
            )
        )

    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(load_settings(self.path), {})

    def test_save_then_load_roundtrip(self):
        save_settings({"target": "Podcast"}, self.path)
        self.assertEqual(load_settings(self.path), {"target": "Podcast"})

    def test_save_creates_missing_directories(self):
        save_settings({"a": 1}, self.path)
        self.assertTrue(os.path.isfile(self.path))

    def test_save_overwrites_previous_value(self):
        save_settings({"target": "YouTube"}, self.path)
        save_settings({"target": "Broadcast"}, self.path)
        self.assertEqual(load_settings(self.path), {"target": "Broadcast"})

    def test_load_corrupt_json_returns_empty_dict(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(load_settings(self.path), {})

    def test_load_non_dict_json_returns_empty_dict(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write('["a", "list"]')
        self.assertEqual(load_settings(self.path), {})

    def test_save_leaves_no_tmp_file_behind(self):
        save_settings({"k": "v"}, self.path)
        self.assertEqual(
            sorted(os.listdir(os.path.dirname(self.path))), ["settings.json"]
        )


# ---------------------------------------------------------------------------
# QueueItem / batch helpers
# ---------------------------------------------------------------------------


def _item(path: str, size: int = 1024, status: str = STATUS_PENDING) -> QueueItem:
    return QueueItem(path=path, size_bytes=size, status=status)


class QueueItemTest(unittest.TestCase):
    def test_basename_strips_directory(self):
        self.assertEqual(_item("/tmp/sub/clip.mp4").basename, "clip.mp4")

    def test_defaults(self):
        item = _item("/tmp/x.mp4")
        self.assertEqual(item.status, STATUS_PENDING)
        self.assertIsNone(item.output_path)
        self.assertIsNone(item.measured)
        self.assertIsNone(item.measured_lufs)


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
