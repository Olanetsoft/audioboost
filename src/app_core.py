"""Headless application core for the AudioBoost GUI.

Owns all state (queue, target, batch worker, analysis worker, waveforms)
and pushes JSON-able snapshots through a callback whenever anything
changes. The webview shell renders snapshots; tests drive the core
directly. No UI toolkit imports here.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import threading
from typing import Callable

from ffmpeg_utils import FFmpegNotFoundError, find_ffmpeg, waveform_png_args
from gui_helpers import (
    QueueItem,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    human_size,
    load_settings,
    save_settings,
    summarize_completion,
)
from processor import (
    DEFAULT_TARGET,
    TARGETS,
    LoudnessTarget,
    NoAudioStreamError,
    ProcessingCancelled,
    ProcessingError,
    Processor,
)

ACCEPTED_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")

WAVE_WIDTH = 512
WAVE_HEIGHT = 56
WAVE_SOURCE_COLOR = "#5d6070"
WAVE_BOOSTED_COLOR = "#7c86ff"

PushCallback = Callable[[dict], None]


def _png_data_uri(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return None


class AppCore:
    def __init__(self, push: PushCallback | None = None) -> None:
        self._push_cb = push or (lambda _s: None)
        self._lock = threading.Lock()

        self.queue: list[QueueItem] = []
        self.processor: Processor | None = None
        self.worker: threading.Thread | None = None
        self._analysis_pending: list[QueueItem] = []
        self._analysis_thread: threading.Thread | None = None

        saved_label = load_settings().get("target")
        self.target: LoudnessTarget = next(
            (t for t in TARGETS if t.label == saved_label), DEFAULT_TARGET
        )

        self.progress_pct: float = 0.0
        self.progress_label: str = ""
        self.summary: str = ""
        self.error: str = ""
        self.error_detail: str = ""

        self._wave_item: QueueItem | None = None
        self._wave_gen = 0
        self._wave_uris: dict[str, str] = {}
        self._wave_tmpdir = tempfile.mkdtemp(prefix="audioboost_wave_")

        try:
            find_ffmpeg()
            self.ffmpeg_missing = False
        except FFmpegNotFoundError:
            self.ffmpeg_missing = True

    # ---------- snapshots ----------

    @property
    def busy(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def snapshot(self) -> dict:
        return {
            "targets": [
                {
                    "label": t.label,
                    "lufs": t.integrated_lufs,
                    "active": t is self.target,
                }
                for t in TARGETS
            ],
            "queue": [
                {
                    "path": item.path,
                    "name": item.basename,
                    "size": human_size(item.size_bytes),
                    "status": item.status,
                    "lufs": item.measured_lufs,
                    "error": item.error_message,
                }
                for item in self.queue
            ],
            "busy": self.busy,
            "canStart": bool(self.queue) and not self.busy,
            "progress": {"pct": self.progress_pct, "label": self.progress_label},
            "summary": self.summary,
            "error": self.error,
            "errorDetail": self.error_detail,
            "ffmpegMissing": self.ffmpeg_missing,
            "wave": {
                "name": self._wave_item.basename if self._wave_item else "",
                "source": self._wave_uris.get("source"),
                "boosted": self._wave_uris.get("boosted"),
            },
            "anySaved": any(
                i.status == STATUS_DONE and i.output_path for i in self.queue
            ),
        }

    def push(self) -> None:
        self._push_cb(self.snapshot())

    # ---------- queue ops ----------

    def add_files(self, paths: list[str]) -> None:
        added = False
        for path in paths:
            if not path or not os.path.isfile(path):
                continue
            if not path.lower().endswith(ACCEPTED_EXTENSIONS):
                self.error = "Unsupported file. Drop an MP4, MOV, MKV, or WebM."
                continue
            if any(item.path == path for item in self.queue):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            item = QueueItem(path=path, size_bytes=size)
            self.queue.append(item)
            added = True
            if not self.busy:
                self._schedule_analysis(item)
        if added and not self.busy:
            self.error = ""
            self.error_detail = ""
            self.summary = ""
            self.progress_pct = 0.0
            self.progress_label = ""
        self.push()

    def clear(self) -> None:
        if self.busy:
            return
        self.queue.clear()
        with self._lock:
            self._analysis_pending.clear()
        self.summary = ""
        self.error = ""
        self.error_detail = ""
        self.progress_pct = 0.0
        self.progress_label = ""
        self._wave_item = None
        self._wave_gen += 1
        self._wave_uris.clear()
        self.push()

    def set_target(self, label: str) -> None:
        if self.busy:
            return
        target = next((t for t in TARGETS if t.label == label), None)
        if target is None:
            return
        self.target = target
        save_settings({**load_settings(), "target": target.label})
        self.push()

    # ---------- background analysis ----------

    def _schedule_analysis(self, item: QueueItem) -> None:
        with self._lock:
            self._analysis_pending.append(item)
        if self._analysis_thread and self._analysis_thread.is_alive():
            return
        self._analysis_thread = threading.Thread(
            target=self._analysis_main, daemon=True
        )
        self._analysis_thread.start()

    def _analysis_main(self) -> None:
        while True:
            with self._lock:
                if not self._analysis_pending:
                    return
                item = self._analysis_pending.pop(0)
            if item not in self.queue or self.busy:
                continue
            target = self.target
            try:
                measured = Processor().analyze(item.path, target=target)
                lufs = float(measured["input_i"])
            except Exception:
                continue
            if item not in self.queue:
                continue
            item.measured = measured
            item.measured_target = target.label
            item.measured_lufs = lufs
            if not self.busy:
                self._show_waveform_for(item)
                self.push()

    # ---------- waveforms ----------

    def _show_waveform_for(self, item: QueueItem) -> None:
        self._wave_item = item
        self._wave_gen += 1
        self._wave_uris.clear()
        self._render_waveform(item.path, WAVE_SOURCE_COLOR, "source",
                              self._wave_gen, item)

    def _render_waveform(
        self, media_path: str, color: str, layer: str, gen: int, item: QueueItem
    ) -> None:
        def worker() -> None:
            try:
                ffmpeg = find_ffmpeg()
                out_png = os.path.join(self._wave_tmpdir, f"{layer}_{gen}.png")
                subprocess.run(
                    waveform_png_args(
                        ffmpeg, media_path, out_png,
                        width=WAVE_WIDTH, height=WAVE_HEIGHT, color=color,
                    ),
                    capture_output=True, timeout=60, check=True,
                )
                uri = _png_data_uri(out_png)
            except Exception:
                return
            if uri is None or gen != self._wave_gen or item is not self._wave_item:
                return
            self._wave_uris[layer] = uri
            self.push()

        threading.Thread(target=worker, daemon=True).start()

    # ---------- batch processing ----------

    def start(self) -> None:
        if self.busy or not self.queue:
            return
        self.error = ""
        self.error_detail = ""
        self.summary = ""
        self.progress_pct = 0.0
        self.progress_label = (
            f"Starting… (target {self.target.integrated_lufs:g} LUFS)"
        )
        with self._lock:
            self._analysis_pending.clear()
        for item in self.queue:
            item.status = STATUS_PENDING
            item.error_message = None
            item.output_path = None
        self.processor = Processor()
        items = list(self.queue)
        target = self.target
        self.worker = threading.Thread(
            target=self._worker_main, args=(items, target), daemon=True
        )
        self.worker.start()
        self.push()

    def cancel(self) -> None:
        if self.processor:
            self.processor.cancel()
        self.progress_label = "Cancelling…"
        self.push()

    def _worker_main(self, items: list[QueueItem], target: LoudnessTarget) -> None:
        assert self.processor is not None
        for item in items:
            if self.processor.cancelled:
                break

            item.status = STATUS_PROCESSING
            self.push()

            def progress_cb(label: str, pct: float, _item: QueueItem = item) -> None:
                new_label = f"{label}  ·  {_item.basename}"
                # Snapshots carry waveform data URIs; throttle the ~10 Hz
                # ffmpeg progress ticks to visible changes only.
                if (
                    new_label == self.progress_label
                    and pct >= 0
                    and abs(pct - self.progress_pct) < 0.5
                ):
                    return
                self.progress_pct = pct
                self.progress_label = new_label
                self.push()

            cached = (
                item.measured
                if item.measured_target == target.label
                else None
            )
            try:
                result = self.processor.process_file(
                    item.path, progress_cb, target=target, measured=cached
                )
            except ProcessingCancelled:
                item.status = STATUS_PENDING
                break
            except FFmpegNotFoundError:
                self.ffmpeg_missing = True
                item.status = STATUS_FAILED
                item.error_message = "FFmpeg not found."
                break
            except NoAudioStreamError as exc:
                item.status = STATUS_FAILED
                item.error_message = str(exc)
            except ProcessingError as exc:
                item.status = STATUS_FAILED
                item.error_message = str(exc)
                tail = exc.stderr_tail.splitlines()[-20:]
                self.error_detail = "\n".join(tail)
            except Exception as exc:  # defensive catch-all
                item.status = STATUS_FAILED
                item.error_message = f"Unexpected error: {exc}"
            else:
                item.status = STATUS_DONE
                item.output_path = result.output_path
                if item is not self._wave_item:
                    self._show_waveform_for(item)
                self._render_waveform(
                    result.output_path, WAVE_BOOSTED_COLOR, "boosted",
                    self._wave_gen, item,
                )
            self.push()

        self._finish_batch()

    def _finish_batch(self) -> None:
        processed = any(
            i.status in (STATUS_DONE, STATUS_FAILED) for i in self.queue
        )
        if not processed:
            self.summary = "Cancelled"
            self.progress_pct = 0.0
        else:
            self.summary = summarize_completion(self.queue)
            self.progress_pct = 100.0
        self.progress_label = ""
        self.push()

    # ---------- shell helpers ----------

    def show_in_finder(self) -> None:
        saved = [i for i in self.queue if i.status == STATUS_DONE and i.output_path]
        if not saved:
            return
        target = saved[0].output_path
        assert target is not None
        if os.path.exists(target):
            subprocess.run(["open", "-R", target], check=False)
