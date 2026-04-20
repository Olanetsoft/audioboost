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


WINDOW_WIDTH = 540
WINDOW_HEIGHT = 440

# Drop zone keeps its own surface color — it's the one place we deliberately
# draw a distinct "card" that contrasts with the window chrome.
DROP_BG = "#ffffff"
DROP_BG_ACTIVE = "#eaf1ff"
DROP_BORDER = "#d1d5db"
DROP_BORDER_ACTIVE = "#3b82f6"
DROP_TEXT = "#4b5563"

MUTED_TEXT = "#6b7280"
ERROR_TEXT = "#b91c1c"
SUCCESS_TEXT = "#15803d"


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
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

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
        # Leave backgrounds alone so ttk labels stay transparent over whatever
        # surface the aqua theme paints. Only set foregrounds + fonts here.
        style.configure("Title.TLabel", font=("SF Pro Display", 20, "bold"))
        style.configure("Subtitle.TLabel", foreground=MUTED_TEXT, font=("SF Pro Text", 12))
        style.configure("Muted.TLabel", foreground=MUTED_TEXT, font=("SF Pro Text", 11))
        style.configure("File.TLabel", font=("SF Pro Text", 12))
        style.configure("Error.TLabel", foreground=ERROR_TEXT, font=("SF Pro Text", 11))
        style.configure("Success.TLabel", foreground=SUCCESS_TEXT, font=("SF Pro Text", 12, "bold"))

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=(22, 20, 22, 18))
        container.pack(fill="both", expand=True)

        # --- header
        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="AudioBoost", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Normalize quiet video audio to -14 LUFS without clipping.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # --- drop zone (the one deliberately custom-styled card)
        drop_wrap = ttk.Frame(container)
        drop_wrap.pack(fill="x", pady=(16, 0))

        self.drop_frame = tk.Frame(
            drop_wrap,
            bg=DROP_BG,
            highlightthickness=2,
            highlightbackground=DROP_BORDER,
            highlightcolor=DROP_BORDER,
            height=180,
            bd=0,
        )
        self.drop_frame.pack(fill="x")
        self.drop_frame.pack_propagate(False)

        drop_inner = tk.Frame(self.drop_frame, bg=DROP_BG)
        drop_inner.pack(expand=True)

        self.drop_icon = tk.Label(
            drop_inner,
            text="⬆",
            bg=DROP_BG,
            fg=DROP_BORDER,
            font=("SF Pro Display", 32),
            cursor="hand2",
        )
        self.drop_icon.pack(pady=(0, 6))

        drop_primary = (
            "Drop an MP4 here" if self._dnd_enabled else "Choose an MP4"
        )
        self.drop_label = tk.Label(
            drop_inner,
            text=drop_primary,
            bg=DROP_BG,
            fg=DROP_TEXT,
            font=("SF Pro Text", 14, "bold"),
            cursor="hand2",
        )
        self.drop_label.pack()

        drop_secondary = "or click to choose a file" if self._dnd_enabled else "click to browse"
        self.drop_hint = tk.Label(
            drop_inner,
            text=drop_secondary,
            bg=DROP_BG,
            fg=MUTED_TEXT,
            font=("SF Pro Text", 11),
            cursor="hand2",
        )
        self.drop_hint.pack(pady=(2, 0))

        for widget in (self.drop_frame, drop_inner, self.drop_icon, self.drop_label, self.drop_hint):
            widget.bind("<Button-1>", lambda _e: self._open_file_picker())

        if self._dnd_enabled:
            self.drop_frame.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropEnter>>", self._on_drop_enter)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropLeave>>", self._on_drop_leave)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]

        # --- selected file row (only visible when a file is chosen)
        self.file_row = ttk.Frame(container)
        self.file_row.pack(fill="x", pady=(14, 0))
        self.file_label = ttk.Label(self.file_row, text="", style="File.TLabel")
        self.file_label.pack(side="left")
        self.clear_button = ttk.Button(
            self.file_row, text="Clear", command=self._clear_selection
        )
        # Packed lazily when a file is selected.

        # --- inline error (hidden when empty to avoid stray baseline artifacts)
        self.inline_error_var = tk.StringVar(value="")
        self.inline_error = ttk.Label(
            container, textvariable=self.inline_error_var, style="Error.TLabel"
        )
        # Packed on demand in _show_error.

        # --- progress
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(
            container, mode="determinate", maximum=100, variable=self.progress_var
        )
        self.progress.pack(fill="x", pady=(16, 6))

        self.status_label = ttk.Label(container, text="", style="Muted.TLabel")
        self.status_label.pack(anchor="w")

        # --- action row pinned to the bottom
        action_row = ttk.Frame(container)
        action_row.pack(side="bottom", fill="x", pady=(14, 0))

        self.process_button = ttk.Button(
            action_row,
            text="Boost Audio",
            command=self._on_process_clicked,
            state="disabled",
        )
        self.process_button.pack(side="left")

        self.cancel_button = ttk.Button(
            action_row, text="Cancel", command=self._on_cancel_clicked
        )
        # Packed lazily during processing.

        self.show_button = ttk.Button(
            action_row, text="Show in Finder", command=self._on_show_in_finder
        )
        self.another_button = ttk.Button(
            action_row, text="Process another", command=self._reset_for_next
        )
        # Completion buttons packed lazily in _show_completion_buttons.

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
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=(22, 18, 22, 16))
        frame.pack()

        ttk.Label(
            frame,
            text="FFmpeg is required",
            font=("SF Pro Display", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Install it with Homebrew, then relaunch AudioBoost:",
            style="Muted.TLabel",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(6, 10))

        cmd = "brew install ffmpeg"
        cmd_entry = tk.Entry(frame, width=34, font=("SF Mono", 12), relief="solid", bd=1)
        cmd_entry.insert(0, cmd)
        cmd_entry.configure(state="readonly")
        cmd_entry.pack(anchor="w", ipady=4)

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(14, 0))
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

    def _paint_drop_zone(self, bg: str, border: str, icon_fg: str) -> None:
        self.drop_frame.configure(
            bg=bg, highlightbackground=border, highlightcolor=border
        )
        for child in self.drop_frame.winfo_children():
            child.configure(bg=bg)
            for sub in child.winfo_children():
                sub.configure(bg=bg)
        self.drop_icon.configure(fg=icon_fg)

    def _on_drop_enter(self, _event) -> None:
        self._paint_drop_zone(DROP_BG_ACTIVE, DROP_BORDER_ACTIVE, DROP_BORDER_ACTIVE)

    def _on_drop_leave(self, _event) -> None:
        self._paint_drop_zone(DROP_BG, DROP_BORDER, DROP_BORDER)

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
        if not self.clear_button.winfo_ismapped():
            self.clear_button.pack(side="right")
        self.process_button.configure(state="normal")

        self.progress_var.set(0.0)
        self.status_label.configure(text="Ready", style="Muted.TLabel")
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
        self.inline_error_var.set(message)
        if not self.inline_error.winfo_ismapped():
            self.inline_error.pack(anchor="w", pady=(6, 0), before=self.progress)

    def _clear_error(self) -> None:
        self.inline_error_var.set("")
        if self.inline_error.winfo_ismapped():
            self.inline_error.pack_forget()

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
        dialog.transient(self.root)
        dialog.geometry("580x380")

        frame = ttk.Frame(dialog, padding=(18, 16, 18, 14))
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text=message, font=("SF Pro Display", 14, "bold")
        ).pack(anchor="w")
        ttk.Label(
            frame, text="Last lines from FFmpeg", style="Muted.TLabel"
        ).pack(anchor="w", pady=(6, 6))

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(
            text_frame, height=12, wrap="none", font=("SF Mono", 11),
            yscrollcommand=scrollbar.set, relief="solid", bd=1,
            bg="#fafafa", fg="#111827",
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=text.yview)

        tail_lines = stderr_tail.splitlines()[-20:]
        text.insert("1.0", "\n".join(tail_lines))
        text.configure(state="disabled")

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(12, 0))
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
