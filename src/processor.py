"""Two-pass loudnorm pipeline for boosting speech audio in MP4s."""

from __future__ import annotations

import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable

from ffmpeg_utils import (
    FFmpegNotFoundError,
    FFprobeError,
    find_ffmpeg,
    parse_loudnorm_json,
    parse_progress_line,
    probe_file,
)

FILTER_PREFIX = (
    "highpass=f=80,"
    "acompressor=threshold=-24dB:ratio=3:attack=20:release=250"
)
LOUDNORM_TARGET = "I=-14:TP=-1.5:LRA=11"


class ProcessingError(RuntimeError):
    """Wraps FFmpeg failures with the tail of stderr for display."""

    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail


class NoAudioStreamError(ProcessingError):
    pass


class ProcessingCancelled(RuntimeError):
    pass


@dataclass
class ProcessResult:
    output_path: str


ProgressCallback = Callable[[str, float], None]
"""(status_label, percent_0_to_100 or -1 for indeterminate)"""


def _unique_output_path(input_path: str) -> str:
    directory = os.path.dirname(os.path.abspath(input_path))
    base, _ = os.path.splitext(os.path.basename(input_path))
    candidate = os.path.join(directory, f"{base}_boosted.mp4")
    i = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_boosted_{i}.mp4")
        i += 1
    return candidate


class Processor:
    """Orchestrates the two-pass FFmpeg pipeline. Supports cooperative cancellation."""

    def __init__(self) -> None:
        self._current_proc: subprocess.Popen | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            if self._current_proc and self._current_proc.poll() is None:
                try:
                    self._current_proc.terminate()
                except ProcessLookupError:
                    pass

    def _check_cancelled(self) -> None:
        if self._cancelled:
            raise ProcessingCancelled()

    def process_file(
        self,
        input_path: str,
        progress_cb: ProgressCallback | None = None,
    ) -> ProcessResult:
        if progress_cb is None:
            progress_cb = lambda _s, _p: None

        ffmpeg = find_ffmpeg()

        try:
            probe = probe_file(input_path)
        except FFprobeError as exc:
            raise ProcessingError(
                f"Could not read file: {exc}", stderr_tail=""
            ) from exc
        if not probe.has_audio:
            raise NoAudioStreamError("This video has no audio track to process.")
        duration_seconds = probe.duration_seconds or 0.0

        self._check_cancelled()
        progress_cb("Analyzing loudness…", -1.0)
        measured = self._run_pass1(ffmpeg, input_path)

        self._check_cancelled()
        output_path = _unique_output_path(input_path)
        try:
            self._run_pass2(
                ffmpeg, input_path, output_path, measured, duration_seconds, progress_cb
            )
        except (ProcessingError, ProcessingCancelled):
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            raise

        progress_cb("Done", 100.0)
        return ProcessResult(output_path=output_path)

    def _run_pass1(self, ffmpeg: str, input_path: str) -> dict:
        filter_arg = (
            f"{FILTER_PREFIX},"
            f"loudnorm={LOUDNORM_TARGET}:print_format=json"
        )
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-i", input_path,
            "-vn",
            "-af", filter_arg,
            "-f", "null",
            "-",
        ]
        stderr_tail: deque[str] = deque(maxlen=200)
        with self._lock:
            if self._cancelled:
                raise ProcessingCancelled()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._current_proc = proc

        assert proc.stderr is not None
        try:
            for line in proc.stderr:
                stderr_tail.append(line)
        finally:
            proc.wait()
            with self._lock:
                self._current_proc = None

        full_stderr = "".join(stderr_tail)
        if self._cancelled:
            raise ProcessingCancelled()
        if proc.returncode != 0:
            raise ProcessingError(
                "FFmpeg analysis pass failed.", stderr_tail=full_stderr
            )
        try:
            return parse_loudnorm_json(full_stderr)
        except ValueError as exc:
            raise ProcessingError(str(exc), stderr_tail=full_stderr) from exc

    def _run_pass2(
        self,
        ffmpeg: str,
        input_path: str,
        output_path: str,
        measured: dict,
        duration_seconds: float,
        progress_cb: ProgressCallback,
    ) -> None:
        filter_arg = (
            f"{FILTER_PREFIX},"
            f"loudnorm={LOUDNORM_TARGET}"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            f":linear=true"
            f":print_format=summary"
        )
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i", input_path,
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-af", filter_arg,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            output_path,
        ]

        stderr_tail: deque[str] = deque(maxlen=200)
        with self._lock:
            if self._cancelled:
                raise ProcessingCancelled()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._current_proc = proc

        stderr_thread = threading.Thread(
            target=self._drain_stderr, args=(proc, stderr_tail), daemon=True
        )
        stderr_thread.start()

        total_us = duration_seconds * 1_000_000 if duration_seconds > 0 else 0
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                parsed = parse_progress_line(line)
                if parsed is None:
                    continue
                key, value = parsed
                if key == "out_time_ms" and total_us > 0:
                    try:
                        current_us = float(value)
                    except ValueError:
                        continue
                    pct = max(0.0, min(99.9, (current_us / total_us) * 100.0))
                    progress_cb("Processing audio…", pct)
                elif key == "progress" and value == "end":
                    progress_cb("Finalizing…", 99.9)
        finally:
            proc.wait()
            stderr_thread.join(timeout=1.0)
            with self._lock:
                self._current_proc = None

        if self._cancelled:
            raise ProcessingCancelled()
        if proc.returncode != 0:
            raise ProcessingError(
                "FFmpeg processing pass failed.",
                stderr_tail="".join(stderr_tail),
            )

    @staticmethod
    def _drain_stderr(proc: subprocess.Popen, sink: deque[str]) -> None:
        if proc.stderr is None:
            return
        for line in proc.stderr:
            sink.append(line)


def process_file(
    input_path: str,
    progress_cb: ProgressCallback | None = None,
) -> ProcessResult:
    """Convenience wrapper for one-shot processing without cancellation."""
    return Processor().process_file(input_path, progress_cb)


__all__ = [
    "FFmpegNotFoundError",
    "FFprobeError",
    "NoAudioStreamError",
    "ProcessingCancelled",
    "ProcessingError",
    "Processor",
    "ProcessResult",
    "process_file",
]
