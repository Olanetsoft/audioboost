"""Tests for pure helpers in processor."""

import os
import tempfile
import unittest

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

from processor import _unique_output_path


class UniqueOutputPathTest(unittest.TestCase):
    def test_new_file_gets_boosted_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "video.mp4")
            open(src, "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "video_boosted.mp4",
            )

    def test_single_collision_increments_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mp4")
            open(src, "w").close()
            open(os.path.join(tmp, "clip_boosted.mp4"), "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "clip_boosted_2.mp4",
            )

    def test_multiple_collisions_keep_incrementing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mp4")
            open(src, "w").close()
            for name in ("clip_boosted.mp4", "clip_boosted_2.mp4", "clip_boosted_3.mp4"):
                open(os.path.join(tmp, name), "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "clip_boosted_4.mp4",
            )

    def test_output_lives_in_source_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mp4")
            open(src, "w").close()
            out = _unique_output_path(src)
            self.assertEqual(os.path.dirname(out), os.path.abspath(tmp))

    def test_preserves_basename_with_dots(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "my.screen.recording.mp4")
            open(src, "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "my.screen.recording_boosted.mp4",
            )


if __name__ == "__main__":
    unittest.main()
