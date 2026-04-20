"""End-to-end tests that invoke a real ffmpeg.

Skipped when ffmpeg isn't available so CI without the binary still passes.
Each test synthesizes a tiny video in a temp directory (~2 seconds, 160x120)
so the full suite stays under a few seconds on modern hardware.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest

from tests import _setup  # noqa: F401  (side-effect: puts src/ on sys.path)

from processor import (
    NoAudioStreamError,
    Processor,
    ProcessingCancelled,
    TARGET_BROADCAST,
    TARGET_PODCAST,
    TARGET_YOUTUBE,
    process_file,
)


def _have_ffmpeg() -> bool:
    try:
        import ffmpeg_utils
        ffmpeg_utils.find_ffmpeg()
        ffmpeg_utils.find_ffprobe()
        return True
    except Exception:
        return False


HAVE_FFMPEG = _have_ffmpeg()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _synth_quiet_mp4(dst: str, *, duration: float = 2.0, volume: float = 0.05) -> None:
    """Create a short silent-video / quiet-tone MP4 at `dst`."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-f", "lavfi", "-i", f"color=c=black:s=160x120:d={duration}",
            "-map", "1:v", "-map", "0:a",
            "-filter:a", f"volume={volume}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            dst,
        ],
        check=True,
    )


def _synth_silent_mp4(dst: str, duration: float = 1.0) -> None:
    """Video with no audio stream — for testing the NoAudioStream path."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=black:s=160x120:d={duration}",
            "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            dst,
        ],
        check=True,
    )


def _synth_quiet_webm_vp9(dst: str, duration: float = 2.0) -> None:
    """WebM with VP9 video — forces the re-encode branch in pass 2."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-f", "lavfi", "-i", f"color=c=black:s=160x120:d={duration}",
            "-map", "1:v", "-map", "0:a",
            "-filter:a", "volume=0.05",
            "-c:v", "libvpx-vp9", "-b:v", "100k", "-cpu-used", "8",
            "-c:a", "libopus", "-b:a", "64k",
            "-shortest",
            dst,
        ],
        check=True,
    )


def _video_codec(path: str) -> str | None:
    import ffmpeg_utils
    return ffmpeg_utils.probe_file(path).video_codec


def _measure_integrated_lufs(path: str, target) -> float:
    """Run loudnorm in analysis mode on `path` and return the measured input_i."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", path,
            "-af", f"loudnorm={target.loudnorm_args}:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, check=True,
    )
    match = re.search(r'"input_i"\s*:\s*"(-?\d+(?:\.\d+)?)"', result.stderr)
    if not match:
        raise AssertionError("Could not find input_i in ffmpeg output")
    return float(match.group(1))


def _video_stream_md5(path: str) -> str:
    """MD5 of the decoded video stream frames. Bit-identical passthrough should
    be exactly preserved across `-c:v copy`."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", path, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg / ffprobe not available on PATH")
class EndToEndTest(unittest.TestCase):
    def test_happy_path_produces_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            _synth_quiet_mp4(src)

            result = process_file(src)

            self.assertTrue(os.path.exists(result.output_path))
            self.assertGreater(os.path.getsize(result.output_path), 1024)
            self.assertEqual(
                os.path.basename(result.output_path), "quiet_boosted.mp4"
            )

    def test_output_loudness_lands_near_youtube_target(self):
        self._assert_loudness_within_tolerance(TARGET_YOUTUBE, tolerance=0.5)

    def test_output_loudness_lands_near_podcast_target(self):
        self._assert_loudness_within_tolerance(TARGET_PODCAST, tolerance=0.5)

    def test_output_loudness_lands_near_broadcast_target(self):
        self._assert_loudness_within_tolerance(TARGET_BROADCAST, tolerance=0.5)

    def _assert_loudness_within_tolerance(self, target, tolerance: float) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            _synth_quiet_mp4(src)
            result = process_file(src, target=target)
            measured = _measure_integrated_lufs(result.output_path, target)
            self.assertAlmostEqual(
                measured, target.integrated_lufs, delta=tolerance,
                msg=(f"expected {target.label} output near "
                     f"{target.integrated_lufs} LUFS, got {measured}"),
            )

    def test_video_stream_is_bit_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            _synth_quiet_mp4(src)
            result = process_file(src)
            self.assertEqual(
                _video_stream_md5(src),
                _video_stream_md5(result.output_path),
                "video stream must be passed through unchanged",
            )

    def test_no_audio_file_raises_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "silent.mp4")
            _synth_silent_mp4(src)
            with self.assertRaises(NoAudioStreamError):
                process_file(src)

    def test_collision_produces_suffixed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mp4")
            _synth_quiet_mp4(src)
            first = process_file(src)
            second = process_file(src)
            self.assertEqual(
                os.path.basename(first.output_path), "clip_boosted.mp4"
            )
            self.assertEqual(
                os.path.basename(second.output_path), "clip_boosted_2.mp4"
            )
            self.assertTrue(os.path.exists(first.output_path))
            self.assertTrue(os.path.exists(second.output_path))

    def test_webm_vp9_input_is_reencoded_to_h264_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.webm")
            _synth_quiet_webm_vp9(src)
            self.assertEqual(_video_codec(src), "vp9")

            result = process_file(src)
            self.assertTrue(os.path.exists(result.output_path))
            self.assertTrue(result.output_path.endswith(".mp4"))
            # VP9 cannot live in MP4, so pass 2 must have re-encoded to h264.
            self.assertEqual(_video_codec(result.output_path), "h264")
            # And the loudness must still land on target.
            measured = _measure_integrated_lufs(result.output_path, TARGET_YOUTUBE)
            self.assertAlmostEqual(
                measured, TARGET_YOUTUBE.integrated_lufs, delta=0.5
            )

    def test_cancel_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "quiet.mp4")
            # Use a ~10s file so we have time to cancel mid-pass-2.
            _synth_quiet_mp4(src, duration=10.0)

            p = Processor()
            events: list[str] = []

            def cb(label: str, _pct: float) -> None:
                events.append(label)
                # Trigger cancel as soon as we see pass 2 start.
                if "Processing" in label and not p._cancelled:
                    p.cancel()

            with self.assertRaises(ProcessingCancelled):
                p.process_file(src, cb)

            leftover = os.path.join(tmp, "quiet_boosted.mp4")
            self.assertFalse(
                os.path.exists(leftover),
                "partial output must be removed on cancel",
            )


if __name__ == "__main__":
    unittest.main()
