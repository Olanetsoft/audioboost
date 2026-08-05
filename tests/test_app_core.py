"""Tests for the headless AppCore that backs the webview GUI.

Fast paths are unit-tested with patched settings; the batch flow runs
against real ffmpeg on tiny synthesized files and is skipped when ffmpeg
is unavailable (same policy as test_integration).
"""

import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

import app_core
from app_core import AppCore
from gui_helpers import STATUS_DONE, STATUS_FAILED
from processor import TARGET_PODCAST, TARGET_YOUTUBE


def _have_ffmpeg() -> bool:
    try:
        import ffmpeg_utils
        ffmpeg_utils.find_ffmpeg()
        ffmpeg_utils.find_ffprobe()
        return True
    except Exception:
        return False


HAVE_FFMPEG = _have_ffmpeg()


def _synth_quiet_mp4(dst: str, duration: float = 2.0) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-f", "lavfi", "-i", f"color=c=black:s=160x120:d={duration}",
            "-map", "1:v", "-map", "0:a",
            "-filter:a", "volume=0.05",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-c:a", "aac", "-shortest",
            dst,
        ],
        check=True,
    )


def _make_core(**kwargs) -> AppCore:
    """AppCore with settings I/O patched out so tests never touch the user's
    real Application Support directory."""
    with patch("app_core.load_settings", return_value={}), \
         patch("app_core.save_settings"):
        return AppCore(**kwargs)


def _wait_until(predicate, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class SnapshotShapeTest(unittest.TestCase):
    def test_initial_snapshot(self):
        core = _make_core()
        s = core.snapshot()
        self.assertEqual([t["label"] for t in s["targets"]],
                         ["YouTube", "Podcast", "Broadcast"])
        self.assertEqual(sum(1 for t in s["targets"] if t["active"]), 1)
        self.assertEqual(s["queue"], [])
        self.assertFalse(s["busy"])
        self.assertFalse(s["canStart"])
        self.assertEqual(s["summary"], "")
        self.assertIn("wave", s)
        self.assertIn("ffmpegMissing", s)

    def test_push_callback_receives_snapshots(self):
        seen = []
        core = _make_core(push=seen.append)
        core.push()
        self.assertEqual(len(seen), 1)
        self.assertIn("queue", seen[0])


class AddFilesTest(unittest.TestCase):
    def setUp(self):
        self.core = _make_core()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _touch(self, name: str) -> str:
        path = os.path.join(self._tmp.name, name)
        with open(path, "wb") as f:
            f.write(b"x" * 100)
        return path

    def test_rejects_unsupported_extension(self):
        path = self._touch("notes.txt")
        self.core.add_files([path])
        self.assertEqual(self.core.queue, [])
        self.assertIn("Unsupported", self.core.error)

    def test_ignores_missing_files(self):
        self.core.add_files(["/nope/missing.mp4"])
        self.assertEqual(self.core.queue, [])

    def test_accepts_and_dedupes(self):
        path = self._touch("clip.mp4")
        self.core.add_files([path, path])
        self.core.add_files([path])
        self.assertEqual(len(self.core.queue), 1)
        self.assertEqual(self.core.queue[0].basename, "clip.mp4")

    def test_can_start_after_add(self):
        self.core.add_files([self._touch("clip.mp4")])
        self.assertTrue(self.core.snapshot()["canStart"])

    def test_clear_resets_queue_and_state(self):
        self.core.add_files([self._touch("clip.mp4")])
        self.core.summary = "✓ Saved 1 file"
        self.core.clear()
        self.assertEqual(self.core.queue, [])
        self.assertEqual(self.core.summary, "")
        self.assertFalse(self.core.snapshot()["canStart"])


class SetTargetTest(unittest.TestCase):
    def test_set_target_switches_and_persists(self):
        core = _make_core()
        with patch("app_core.load_settings", return_value={}), \
             patch("app_core.save_settings") as save:
            core.set_target("Podcast")
        self.assertIs(core.target, TARGET_PODCAST)
        save.assert_called_once()
        self.assertEqual(save.call_args[0][0]["target"], "Podcast")

    def test_unknown_label_is_ignored(self):
        core = _make_core()
        before = core.target
        core.set_target("Cinema")
        self.assertIs(core.target, before)

    def test_saved_target_restored_at_startup(self):
        with patch("app_core.load_settings", return_value={"target": "Broadcast"}):
            core = AppCore()
        self.assertEqual(core.target.label, "Broadcast")

    def test_bad_saved_target_falls_back_to_default(self):
        with patch("app_core.load_settings", return_value={"target": "Nope"}):
            core = AppCore()
        self.assertIs(core.target, TARGET_YOUTUBE)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg / ffprobe not available on PATH")
class BatchFlowTest(unittest.TestCase):
    def test_batch_processes_and_summarizes(self):
        events: list[dict] = []
        core = _make_core(push=events.append)
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            _synth_quiet_mp4(src)
            core.add_files([src])

            core.start()
            self.assertTrue(
                _wait_until(lambda: not core.busy and core.summary),
                "batch did not finish in time",
            )

            item = core.queue[0]
            self.assertEqual(item.status, STATUS_DONE)
            self.assertTrue(item.output_path and os.path.exists(item.output_path))
            self.assertEqual(core.summary, "✓ Saved 1 file")
            self.assertTrue(core.snapshot()["anySaved"])
            # waveforms render asynchronously after completion
            self.assertTrue(
                _wait_until(lambda: core.snapshot()["wave"]["boosted"]),
                "boosted waveform never rendered",
            )
            self.assertTrue(
                core.snapshot()["wave"]["source"].startswith("data:image/png;base64,")
            )
            # progress pushes were throttled but present
            self.assertTrue(any(e["busy"] for e in events))

    def test_failure_continues_batch(self):
        core = _make_core()
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "good.mp4")
            _synth_quiet_mp4(good)
            silent = os.path.join(tmp, "silent.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1",
                 "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-preset", "ultrafast", silent],
                check=True,
            )
            core.add_files([silent, good])
            core.start()
            self.assertTrue(
                _wait_until(lambda: not core.busy and core.summary),
                "batch did not finish in time",
            )
            statuses = {i.basename: i.status for i in core.queue}
            self.assertEqual(statuses["silent.mp4"], STATUS_FAILED)
            self.assertEqual(statuses["good.mp4"], STATUS_DONE)
            self.assertEqual(core.summary, "Done: 1 saved · 1 failed")

    def test_analysis_populates_lufs_and_waveform(self):
        core = _make_core()
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            _synth_quiet_mp4(src)
            core.add_files([src])
            self.assertTrue(
                _wait_until(lambda: core.queue[0].measured_lufs is not None),
                "analysis never completed",
            )
            self.assertLess(core.queue[0].measured_lufs, -20)
            self.assertTrue(
                _wait_until(lambda: core.snapshot()["wave"]["source"]),
                "source waveform never rendered",
            )


if __name__ == "__main__":
    unittest.main()
