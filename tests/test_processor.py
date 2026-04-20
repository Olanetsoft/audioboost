"""Tests for pure helpers in processor."""

import os
import tempfile
import unittest

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

from processor import (
    DEFAULT_TARGET,
    TARGET_BROADCAST,
    TARGET_PODCAST,
    TARGET_YOUTUBE,
    TARGETS,
    _unique_output_path,
)


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


class LoudnessTargetTest(unittest.TestCase):
    def test_youtube_preset(self):
        self.assertEqual(TARGET_YOUTUBE.integrated_lufs, -14.0)
        self.assertEqual(TARGET_YOUTUBE.true_peak_db, -1.5)
        self.assertEqual(TARGET_YOUTUBE.loudnorm_args, "I=-14.0:TP=-1.5:LRA=11.0")

    def test_podcast_preset(self):
        self.assertEqual(TARGET_PODCAST.integrated_lufs, -16.0)
        self.assertEqual(TARGET_PODCAST.loudnorm_args, "I=-16.0:TP=-1.5:LRA=11.0")

    def test_broadcast_preset(self):
        self.assertEqual(TARGET_BROADCAST.integrated_lufs, -23.0)
        self.assertEqual(TARGET_BROADCAST.true_peak_db, -1.0)
        self.assertEqual(TARGET_BROADCAST.lra, 20.0)

    def test_default_is_youtube(self):
        self.assertIs(DEFAULT_TARGET, TARGET_YOUTUBE)

    def test_targets_tuple_lists_all_three(self):
        self.assertEqual(TARGETS, (TARGET_YOUTUBE, TARGET_PODCAST, TARGET_BROADCAST))


if __name__ == "__main__":
    unittest.main()
