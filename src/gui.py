"""Tkinter UI with drag-and-drop for AudioBoost."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ffmpeg_utils import FFmpegNotFoundError, find_ffmpeg
from processor import (
    NoAudioStreamError,
    ProcessingCancelled,
    ProcessingError,
    Processor,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except Exception:  # pragma: no cover - import-time fallback only
    TkinterDnD = None  # type: ignore
    DND_FILES = None  # type: ignore
    _HAS_DND = False


WINDOW_SIZE = "520x400"
ACCENTED_BG = "#f4f6fa"
DROP_BG = "#ffffff"
DROP_BG_ACTIVE = "#e6f0ff"
DROP_BORDER = "#c2cad9"
DROP_BORDER_ACTIVE = "#4f7cff"
MUTED_TEXT = "#6b7280"
ERROR_TEXT = "#c0392b"
SUCCESS_TEXT = "#1e7e34"


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024 or unit == "TB":
            if unit == "B":
                return f"{nbytes} {unit}"
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} TB"


def _parse_dnd_paths(data: str) -> list[str]:
    """tkdnd delivers file lists as space-separated, with braces for paths containing spaces."""
    paths: list[str] = []
    buf = ""
    in_brace = False
    for ch in data:
        if ch == "{":
            in_brace = True
            continue
        if ch == "}":
            in_brace = False
            paths.append(buf)
            buf = ""
            continue
        if ch == " " and not in_brace:
            if buf:
                paths.append(buf)
                buf = ""
            continue
        buf += ch
    if buf:
        paths.append(buf)
    return paths


class AudioBoostApp:
    def __init__(self) -> None:
        self._dnd_enabled = False
        self.root = None  # type: ignore[assignment]
        if _HAS_DND:
            try:
                self.root = TkinterDnD.Tk()
                self._dnd_enabled = True
            except Exception:
                # tkdnd native library ABI mismatch with Tcl/Tk 9 — fall back.
                self.root = None  # type: ignore[assignment]
        if self.root is None:
            self.root = tk.Tk()

        self.root.title("AudioBoost")
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(False, False)
        self.root.configure(bg=ACCENTED_BG)

        self._selected_path: str | None = None
        self._processor: Processor | None = None
        self._worker: threading.Thread | None = None

        self._build_style()
        self._build_layout()

        self.root.after(100, self._check_ffmpeg_on_launch)

    # ---------- styling & layout ----------

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("aqua")
        except tk.TclError:
            pass
        style.configure("Muted.TLabel", foreground=MUTED_TEXT, background=ACCENTED_BG)
        style.configure("Error.TLabel", foreground=ERROR_TEXT, background=ACCENTED_BG)
        style.configure("Success.TLabel", foreground=SUCCESS_TEXT, background=ACCENTED_BG)
        style.configure("Title.TLabel", font=("SF Pro Display", 18, "bold"), background=ACCENTED_BG)
        style.configure("TLabel", background=ACCENTED_BG)

    def _build_layout(self) -> None:
        container = tk.Frame(self.root, bg=ACCENTED_BG, padx=20, pady=18)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="AudioBoost", style="Title.TLabel")
        title.pack(anchor="w")
        subtitle = ttk.Label(
            container,
            text="Drop an MP4 to normalize its audio to YouTube loudness (-14 LUFS).",
            style="Muted.TLabel",
        )
        subtitle.pack(anchor="w", pady=(2, 12))

        self.drop_frame = tk.Frame(
            container,
            bg=DROP_BG,
            highlightthickness=2,
            highlightbackground=DROP_BORDER,
            highlightcolor=DROP_BORDER,
            height=170,
        )
        self.drop_frame.pack(fill="x", expand=False)
        self.drop_frame.pack_propagate(False)

        drop_text = (
            "Drop an MP4 here\n\nor click to choose a file"
            if self._dnd_enabled
            else "Click to choose an MP4"
        )
        self.drop_label = tk.Label(
            self.drop_frame,
            text=drop_text,
            bg=DROP_BG,
            fg=MUTED_TEXT,
            font=("SF Pro Text", 13),
            justify="center",
            cursor="hand2",
        )
        self.drop_label.pack(expand=True, fill="both", padx=10, pady=10)
        self.drop_label.bind("<Button-1>", lambda _e: self._open_file_picker())
        self.drop_frame.bind("<Button-1>", lambda _e: self._open_file_picker())

        if self._dnd_enabled:
            self.drop_frame.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropEnter>>", self._on_drop_enter)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropLeave>>", self._on_drop_leave)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]

        self.file_row = tk.Frame(container, bg=ACCENTED_BG)
        self.file_row.pack(fill="x", pady=(10, 4))
        self.file_label = ttk.Label(self.file_row, text="", style="Muted.TLabel")
        self.file_label.pack(side="left")
        self.clear_button = ttk.Button(self.file_row, text="✕ Clear", command=self._clear_selection)
        self.clear_button.pack(side="right")
        self.clear_button.pack_forget()

        self.inline_error = ttk.Label(container, text="", style="Error.TLabel")
        self.inline_error.pack(anchor="w")

        action_row = tk.Frame(container, bg=ACCENTED_BG)
        action_row.pack(fill="x", pady=(12, 6))
        self.process_button = ttk.Button(
            action_row, text="Boost Audio", command=self._on_process_clicked, state="disabled"
        )
        self.process_button.pack(side="left")
        self.cancel_button = ttk.Button(
            action_row, text="Cancel", command=self._on_cancel_clicked
        )
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.cancel_button.pack_forget()

        self.show_button = ttk.Button(
            action_row, text="Show in Finder", command=self._on_show_in_finder
        )
        self.another_button = ttk.Button(
            action_row, text="Process another", command=self._reset_for_next
        )

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(
            container, mode="determinate", maximum=100, variable=self.progress_var
        )
        self.progress.pack(fill="x", pady=(10, 4))
        self.status_label = ttk.Label(container, text="", style="Muted.TLabel")
        self.status_label.pack(anchor="w")

        self._last_output: str | None = None

    # ---------- ffmpeg sanity ----------

    def _check_ffmpeg_on_launch(self) -> None:
        try:
            find_ffmpeg()
        except FFmpegNotFoundError:
            self._show_ffmpeg_missing_dialog()

    def _show_ffmpeg_missing_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("FFmpeg required")
        dialog.configure(bg=ACCENTED_BG)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = tk.Frame(dialog, bg=ACCENTED_BG, padx=20, pady=16)
        frame.pack()

        ttk.Label(
            frame,
            text="FFmpeg is required.",
            font=("SF Pro Display", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Install it with Homebrew, then relaunch AudioBoost:",
            style="Muted.TLabel",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(6, 8))

        cmd = "brew install ffmpeg"
        cmd_entry = tk.Entry(frame, width=36, font=("SF Mono", 12))
        cmd_entry.insert(0, cmd)
        cmd_entry.configure(state="readonly")
        cmd_entry.pack(anchor="w")

        buttons = tk.Frame(frame, bg=ACCENTED_BG)
        buttons.pack(anchor="e", pady=(12, 0))
        ttk.Button(
            buttons,
            text="Copy command",
            command=lambda: self._copy_to_clipboard(cmd),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Quit", command=self.root.destroy).pack(side="left")

    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # ---------- file selection ----------

    def _open_file_picker(self) -> None:
        if self.process_button.instate(["disabled"]) and self._worker and self._worker.is_alive():
            return
        path = filedialog.askopenfilename(
            title="Choose an MP4",
            filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
        )
        if path:
            self._accept_file(path)

    def _on_drop_enter(self, _event) -> None:
        self.drop_frame.configure(
            bg=DROP_BG_ACTIVE, highlightbackground=DROP_BORDER_ACTIVE, highlightcolor=DROP_BORDER_ACTIVE
        )
        self.drop_label.configure(bg=DROP_BG_ACTIVE)

    def _on_drop_leave(self, _event) -> None:
        self.drop_frame.configure(
            bg=DROP_BG, highlightbackground=DROP_BORDER, highlightcolor=DROP_BORDER
        )
        self.drop_label.configure(bg=DROP_BG)

    def _on_drop(self, event) -> None:
        self._on_drop_leave(event)
        paths = _parse_dnd_paths(event.data)
        if not paths:
            return
        self._accept_file(paths[0])

    def _accept_file(self, path: str) -> None:
        self._clear_error()
        if not os.path.isfile(path):
            self._show_error("File not found.")
            return
        if not path.lower().endswith(".mp4"):
            self._show_error("Please drop an MP4 file.")
            return

        self._selected_path = path
        try:
            size_str = _human_size(os.path.getsize(path))
        except OSError:
            size_str = "—"
        self.file_label.configure(text=f"{os.path.basename(path)}  ·  {size_str}")
        self.clear_button.pack(side="right")
        self.process_button.configure(state="normal")

        self.progress_var.set(0.0)
        self.status_label.configure(text="Ready.", style="Muted.TLabel")
        self._hide_completion_buttons()

    def _clear_selection(self) -> None:
        self._selected_path = None
        self.file_label.configure(text="")
        self.clear_button.pack_forget()
        self.process_button.configure(state="disabled")
        self.progress_var.set(0.0)
        self.status_label.configure(text="", style="Muted.TLabel")
        self._clear_error()
        self._hide_completion_buttons()

    # ---------- inline error ----------

    def _show_error(self, message: str) -> None:
        self.inline_error.configure(text=message)

    def _clear_error(self) -> None:
        self.inline_error.configure(text="")

    # ---------- processing ----------

    def _on_process_clicked(self) -> None:
        if not self._selected_path:
            return
        self._clear_error()
        self._hide_completion_buttons()
        self.progress_var.set(0.0)
        self.status_label.configure(text="Starting…", style="Muted.TLabel")
        self.process_button.configure(state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))

        self._processor = Processor()
        input_path = self._selected_path
        self._worker = threading.Thread(
            target=self._worker_main, args=(input_path,), daemon=True
        )
        self._worker.start()

    def _on_cancel_clicked(self) -> None:
        if self._processor:
            self._processor.cancel()
        self.status_label.configure(text="Cancelling…", style="Muted.TLabel")
        self.cancel_button.configure(state="disabled")

    def _worker_main(self, input_path: str) -> None:
        def progress_cb(label: str, pct: float) -> None:
            self.root.after(0, self._apply_progress, label, pct)

        assert self._processor is not None
        try:
            result = self._processor.process_file(input_path, progress_cb)
        except ProcessingCancelled:
            self.root.after(0, self._on_processing_cancelled)
        except NoAudioStreamError as exc:
            self.root.after(0, self._on_processing_error, str(exc), "", False)
        except ProcessingError as exc:
            self.root.after(0, self._on_processing_error, str(exc), exc.stderr_tail, True)
        except FFmpegNotFoundError:
            self.root.after(0, self._show_ffmpeg_missing_dialog)
            self.root.after(0, self._reset_after_failure)
        except Exception as exc:  # defensive catch-all
            self.root.after(0, self._on_processing_error, f"Unexpected error: {exc}", "", True)
        else:
            self.root.after(0, self._on_processing_done, result.output_path)

    # ---------- UI callbacks from worker ----------

    def _apply_progress(self, label: str, pct: float) -> None:
        if pct < 0:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress_var.set(pct)
        self.status_label.configure(text=label, style="Muted.TLabel")

    def _on_processing_done(self, output_path: str) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(100.0)
        self._last_output = output_path
        self.status_label.configure(
            text=f"✓ Saved as {os.path.basename(output_path)}", style="Success.TLabel"
        )
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self._show_completion_buttons()

    def _on_processing_cancelled(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.status_label.configure(text="Cancelled.", style="Muted.TLabel")
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        if self._selected_path:
            self.process_button.configure(state="normal")

    def _on_processing_error(self, message: str, stderr_tail: str, show_details: bool) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self.status_label.configure(text="Failed.", style="Error.TLabel")
        if self._selected_path:
            self.process_button.configure(state="normal")
        if show_details and stderr_tail:
            self._show_error_dialog(message, stderr_tail)
        else:
            self._show_error(message)

    def _reset_after_failure(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        if self._selected_path:
            self.process_button.configure(state="normal")

    def _show_error_dialog(self, message: str, stderr_tail: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Processing error")
        dialog.configure(bg=ACCENTED_BG)
        dialog.transient(self.root)
        dialog.geometry("560x360")

        frame = tk.Frame(dialog, bg=ACCENTED_BG, padx=16, pady=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text=message, font=("SF Pro Display", 13, "bold")
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Last lines from FFmpeg:",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(6, 4))

        text_frame = tk.Frame(frame, bg=ACCENTED_BG)
        text_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(
            text_frame, height=12, wrap="none", font=("SF Mono", 11),
            yscrollcommand=scrollbar.set,
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=text.yview)

        tail_lines = stderr_tail.splitlines()[-20:]
        text.insert("1.0", "\n".join(tail_lines))
        text.configure(state="disabled")

        buttons = tk.Frame(frame, bg=ACCENTED_BG)
        buttons.pack(anchor="e", pady=(10, 0))
        ttk.Button(
            buttons,
            text="Copy error",
            command=lambda: self._copy_to_clipboard("\n".join(tail_lines)),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left")

    # ---------- completion buttons ----------

    def _show_completion_buttons(self) -> None:
        self.show_button.pack(side="left", padx=(0, 8))
        self.another_button.pack(side="left")

    def _hide_completion_buttons(self) -> None:
        self.show_button.pack_forget()
        self.another_button.pack_forget()

    def _on_show_in_finder(self) -> None:
        if not self._last_output or not os.path.exists(self._last_output):
            return
        try:
            subprocess.run(["open", "-R", self._last_output], check=False)
        except FileNotFoundError:
            pass

    def _reset_for_next(self) -> None:
        self._clear_selection()
        self._last_output = None

    # ---------- entry ----------

    def run(self) -> None:
        self.root.mainloop()


def run_app() -> None:
    AudioBoostApp().run()
