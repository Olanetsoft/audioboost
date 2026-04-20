"""Tests for processor: filter-chain assembly, error wrapping, cancellation,
output-path collision handling, loudness-target presets."""

import io
import os
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

import processor
from ffmpeg_utils import FFmpegNotFoundError, FFprobeError, ProbeResult
from processor import (
    DEFAULT_TARGET,
    FILTER_PREFIX,
    LoudnessTarget,
    NoAudioStreamError,
    Processor,
    ProcessingCancelled,
    ProcessingError,
    TARGETS,
    TARGET_BROADCAST,
    TARGET_PODCAST,
    TARGET_YOUTUBE,
    _unique_output_path,
)


SAMPLE_LOUDNORM_JSON = """
[Parsed_loudnorm @ 0xabc]
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


def _fake_popen(*, stdout_lines=(), stderr_lines=(), returncode=0) -> MagicMock:
    """Build a MagicMock that mimics a finished subprocess.Popen."""
    proc = MagicMock(name="Popen")
    proc.stdout = io.StringIO("".join(stdout_lines))
    proc.stderr = io.StringIO("".join(stderr_lines))
    proc.returncode = returncode
    proc.poll.return_value = returncode
    proc.wait.return_value = returncode
    return proc


# ---------------------------------------------------------------------------
# LoudnessTarget
# ---------------------------------------------------------------------------


class LoudnessTargetTest(unittest.TestCase):
    def test_youtube_preset_values(self):
        self.assertEqual(TARGET_YOUTUBE.integrated_lufs, -14.0)
        self.assertEqual(TARGET_YOUTUBE.true_peak_db, -1.5)
        self.assertEqual(TARGET_YOUTUBE.lra, 11.0)

    def test_podcast_preset_values(self):
        self.assertEqual(TARGET_PODCAST.integrated_lufs, -16.0)
        self.assertEqual(TARGET_PODCAST.true_peak_db, -1.5)

    def test_broadcast_preset_values(self):
        # EBU R128 spec: -23 LUFS, -1 dBTP, LRA 20
        self.assertEqual(TARGET_BROADCAST.integrated_lufs, -23.0)
        self.assertEqual(TARGET_BROADCAST.true_peak_db, -1.0)
        self.assertEqual(TARGET_BROADCAST.lra, 20.0)

    def test_loudnorm_args_youtube_exact(self):
        self.assertEqual(TARGET_YOUTUBE.loudnorm_args, "I=-14.0:TP=-1.5:LRA=11.0")

    def test_loudnorm_args_podcast_exact(self):
        self.assertEqual(TARGET_PODCAST.loudnorm_args, "I=-16.0:TP=-1.5:LRA=11.0")

    def test_loudnorm_args_broadcast_exact(self):
        self.assertEqual(TARGET_BROADCAST.loudnorm_args, "I=-23.0:TP=-1.0:LRA=20.0")

    def test_default_target_is_youtube(self):
        self.assertIs(DEFAULT_TARGET, TARGET_YOUTUBE)

    def test_targets_tuple_lists_all_three_in_order(self):
        self.assertEqual(TARGETS, (TARGET_YOUTUBE, TARGET_PODCAST, TARGET_BROADCAST))

    def test_loudness_target_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            TARGET_YOUTUBE.integrated_lufs = -20.0  # type: ignore[misc]

    def test_custom_target_constructs(self):
        custom = LoudnessTarget("Custom", -18.0, -2.0, 9.0)
        self.assertEqual(custom.loudnorm_args, "I=-18.0:TP=-2.0:LRA=9.0")


# ---------------------------------------------------------------------------
# _unique_output_path
# ---------------------------------------------------------------------------


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

    def test_preserves_basename_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "my clip.mp4")
            open(src, "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "my clip_boosted.mp4",
            )

    def test_extensionless_input_still_gets_mp4_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "video")
            open(src, "w").close()
            self.assertEqual(
                os.path.basename(_unique_output_path(src)),
                "video_boosted.mp4",
            )

    def test_accepts_relative_path_and_returns_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                open("clip.mp4", "w").close()
                out = _unique_output_path("clip.mp4")
                self.assertTrue(os.path.isabs(out))
                self.assertEqual(os.path.basename(out), "clip_boosted.mp4")
            finally:
                os.chdir(cwd)


# ---------------------------------------------------------------------------
# Filter-chain assembly via mocked subprocess.Popen
# ---------------------------------------------------------------------------


class FilterChainAssemblyTest(unittest.TestCase):
    """Verify the ffmpeg command lines Processor constructs for each pass."""

    def _run_processor(self, target: LoudnessTarget = TARGET_YOUTUBE):
        """Run process_file with Popen mocked; return (pass1_cmd, pass2_cmd)."""
        captured: list[list[str]] = []

        def popen_side_effect(cmd, *args, **kwargs):
            captured.append(cmd)
            # Pass 1 writes loudnorm JSON to stderr; pass 2 writes progress to stdout.
            if "-vn" in cmd and "-f" in cmd and "null" in cmd:
                return _fake_popen(stderr_lines=[SAMPLE_LOUDNORM_JSON])
            return _fake_popen(
                stdout_lines=["out_time_ms=0\nprogress=end\n"],
                stderr_lines=["ok\n"],
            )

        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=10.0, has_audio=True)), \
             patch("processor._unique_output_path", return_value="/tmp/out.mp4"), \
             patch("processor.subprocess.Popen", side_effect=popen_side_effect):
            processor.process_file("/tmp/in.mp4", target=target)

        self.assertEqual(len(captured), 2, "expected exactly two ffmpeg invocations")
        return captured[0], captured[1]

    def _af_arg(self, cmd: list[str]) -> str:
        return cmd[cmd.index("-af") + 1]

    def test_pass1_uses_correct_ffmpeg_binary(self):
        pass1, _ = self._run_processor()
        self.assertEqual(pass1[0], "/usr/bin/ffmpeg")

    def test_pass1_disables_video_and_writes_to_null(self):
        pass1, _ = self._run_processor()
        self.assertIn("-vn", pass1)
        self.assertIn("-f", pass1)
        self.assertEqual(pass1[-1], "-")

    def test_pass1_filter_includes_highpass_compressor_loudnorm(self):
        pass1, _ = self._run_processor()
        af = self._af_arg(pass1)
        self.assertIn("highpass=f=80", af)
        self.assertIn("acompressor=", af)
        self.assertIn("loudnorm=", af)
        self.assertIn("print_format=json", af)

    def test_pass1_uses_target_lufs_value(self):
        for target in TARGETS:
            pass1, _ = self._run_processor(target)
            self.assertIn(target.loudnorm_args, self._af_arg(pass1))

    def test_pass2_copies_video_stream(self):
        _, pass2 = self._run_processor()
        vc_idx = pass2.index("-c:v")
        self.assertEqual(pass2[vc_idx + 1], "copy")

    def test_pass2_reencodes_audio_as_aac_192k(self):
        _, pass2 = self._run_processor()
        ac_idx = pass2.index("-c:a")
        self.assertEqual(pass2[ac_idx + 1], "aac")
        br_idx = pass2.index("-b:a")
        self.assertEqual(pass2[br_idx + 1], "192k")

    def test_pass2_emits_faststart_mp4(self):
        _, pass2 = self._run_processor()
        mv_idx = pass2.index("-movflags")
        self.assertEqual(pass2[mv_idx + 1], "+faststart")

    def test_pass2_filter_applies_measured_values_from_pass1(self):
        _, pass2 = self._run_processor()
        af = self._af_arg(pass2)
        self.assertIn("measured_I=-28.45", af)
        self.assertIn("measured_TP=-12.34", af)
        self.assertIn("measured_LRA=7.20", af)
        self.assertIn("measured_thresh=-38.67", af)
        self.assertIn("offset=0.02", af)
        self.assertIn("linear=true", af)

    def test_pass2_output_path_is_last_arg(self):
        _, pass2 = self._run_processor()
        self.assertEqual(pass2[-1], "/tmp/out.mp4")

    def test_pass2_requests_progress_pipe(self):
        _, pass2 = self._run_processor()
        p_idx = pass2.index("-progress")
        self.assertEqual(pass2[p_idx + 1], "pipe:1")
        self.assertIn("-nostats", pass2)

    def test_filter_prefix_constant_shape(self):
        # Encodes the public contract: highpass first, then compressor, then loudnorm
        self.assertTrue(FILTER_PREFIX.startswith("highpass=f=80"))
        self.assertIn("acompressor=threshold=-24dB", FILTER_PREFIX)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class ProcessFileErrorPathsTest(unittest.TestCase):
    def test_no_audio_stream_raises_specific_exception(self):
        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=5.0, has_audio=False)):
            with self.assertRaises(NoAudioStreamError):
                processor.process_file("/tmp/silent.mp4")

    def test_ffprobe_failure_wrapped_as_processing_error(self):
        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file", side_effect=FFprobeError("nope")):
            with self.assertRaises(ProcessingError) as cm:
                processor.process_file("/tmp/x.mp4")
            self.assertIn("nope", str(cm.exception))
            # must NOT be NoAudioStreamError — that's a different category
            self.assertNotIsInstance(cm.exception, NoAudioStreamError)

    def test_missing_ffmpeg_bubbles_up(self):
        with patch("processor.find_ffmpeg", side_effect=FFmpegNotFoundError("x")):
            with self.assertRaises(FFmpegNotFoundError):
                processor.process_file("/tmp/x.mp4")

    def test_pass1_failure_produces_processing_error_with_stderr_tail(self):
        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=5.0, has_audio=True)), \
             patch("processor.subprocess.Popen",
                   return_value=_fake_popen(stderr_lines=["[err] fatal\n"], returncode=1)):
            with self.assertRaises(ProcessingError) as cm:
                processor.process_file("/tmp/x.mp4")
            self.assertIn("fatal", cm.exception.stderr_tail)

    def test_pass1_unparseable_output_produces_processing_error(self):
        # pass 1 exits 0 but stderr has no loudnorm JSON block
        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=5.0, has_audio=True)), \
             patch("processor.subprocess.Popen",
                   return_value=_fake_popen(stderr_lines=["no JSON here\n"])):
            with self.assertRaises(ProcessingError):
                processor.process_file("/tmp/x.mp4")

    def test_pass2_failure_cleans_up_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.mp4")
            out = os.path.join(tmp, "out.mp4")
            open(src, "w").close()
            # Simulate a partial output file that pass 2 left behind.
            with open(out, "wb") as f:
                f.write(b"partial")

            call = {"n": 0}

            def popen_side_effect(cmd, *args, **kwargs):
                call["n"] += 1
                if call["n"] == 1:
                    return _fake_popen(stderr_lines=[SAMPLE_LOUDNORM_JSON])
                return _fake_popen(
                    stdout_lines=["out_time_ms=0\nprogress=end\n"],
                    stderr_lines=["fatal\n"],
                    returncode=1,
                )

            with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
                 patch("processor.probe_file",
                       return_value=ProbeResult(duration_seconds=5.0, has_audio=True)), \
                 patch("processor._unique_output_path", return_value=out), \
                 patch("processor.subprocess.Popen", side_effect=popen_side_effect):
                with self.assertRaises(ProcessingError):
                    processor.process_file(src)

            self.assertFalse(os.path.exists(out),
                             "partial output must be removed on failure")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class CancellationTest(unittest.TestCase):
    def test_cancel_before_start_raises_processing_cancelled(self):
        p = Processor()
        p.cancel()
        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=5.0, has_audio=True)), \
             patch("processor.subprocess.Popen",
                   return_value=_fake_popen(stderr_lines=[SAMPLE_LOUDNORM_JSON])):
            with self.assertRaises(ProcessingCancelled):
                p.process_file("/tmp/x.mp4")

    def test_cancel_is_safe_when_no_subprocess_running(self):
        p = Processor()
        p.cancel()  # must not raise
        p.cancel()  # idempotent
        self.assertTrue(p._cancelled)  # internal flag set

    def test_cancel_terminates_current_subprocess(self):
        p = Processor()
        proc = MagicMock()
        proc.poll.return_value = None  # still running
        p._current_proc = proc
        p.cancel()
        proc.terminate.assert_called_once()

    def test_cancel_tolerates_process_lookup_error(self):
        # Race: process exits between poll() and terminate(). Should not crash.
        p = Processor()
        proc = MagicMock()
        proc.poll.return_value = None
        proc.terminate.side_effect = ProcessLookupError
        p._current_proc = proc
        p.cancel()  # must not raise

    def test_progress_callback_receives_analyzing_then_done(self):
        """Happy-path progress sequence reaches 'Done' at 100%."""
        events: list[tuple[str, float]] = []

        def cb(label: str, pct: float) -> None:
            events.append((label, pct))

        with patch("processor.find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
             patch("processor.probe_file",
                   return_value=ProbeResult(duration_seconds=5.0, has_audio=True)), \
             patch("processor._unique_output_path", return_value="/tmp/o.mp4"), \
             patch("processor.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = [
                _fake_popen(stderr_lines=[SAMPLE_LOUDNORM_JSON]),
                _fake_popen(
                    stdout_lines=["out_time_ms=2500000\n", "progress=end\n"],
                    stderr_lines=["ok\n"],
                ),
            ]
            processor.process_file("/tmp/in.mp4", cb)

        labels = [label for label, _ in events]
        self.assertEqual(labels[0], "Analyzing loudness…")
        self.assertEqual(events[-1], ("Done", 100.0))
        # Progress must be monotonically non-decreasing while positive.
        pcts = [pct for _, pct in events if pct >= 0]
        self.assertEqual(pcts, sorted(pcts))


if __name__ == "__main__":
    unittest.main()
