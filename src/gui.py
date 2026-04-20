"""Tkinter UI with drag-and-drop for AudioBoost."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ffmpeg_utils import FFmpegNotFoundError, find_ffmpeg
from gui_helpers import Palette, human_size, is_dark_mode, parse_dnd_paths
from processor import (
    DEFAULT_TARGET,
    TARGETS,
    LoudnessTarget,
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


WINDOW_WIDTH = 560
WINDOW_HEIGHT = 560


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

        self.palette = Palette(dark=is_dark_mode())

        self.root.title("AudioBoost")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._selected_path: str | None = None
        self._processor: Processor | None = None
        self._worker: threading.Thread | None = None
        self._current_target: LoudnessTarget = DEFAULT_TARGET
        self._segment_buttons: dict[LoudnessTarget, tk.Label] = {}
        self._segments_enabled: bool = True
        self._primary_enabled: bool = False

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
        p = self.palette
        style.configure("Title.TLabel", font=("SF Pro Display", 22, "bold"))
        style.configure("Subtitle.TLabel", foreground=p.muted, font=("SF Pro Text", 12))
        style.configure("Muted.TLabel", foreground=p.muted, font=("SF Pro Text", 11))
        style.configure("File.TLabel", font=("SF Pro Text", 12))
        style.configure("Error.TLabel", foreground=p.error, font=("SF Pro Text", 11))
        style.configure("Success.TLabel", foreground=p.success, font=("SF Pro Text", 12, "bold"))
        # aqua ignores most Progressbar overrides, but troughcolor + background
        # land on newer Tk builds — harmless to try on older ones.
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=p.segment_bg,
            background=p.accent,
            bordercolor=p.segment_bg,
            lightcolor=p.accent,
            darkcolor=p.accent,
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=(24, 20, 24, 20))
        container.pack(fill="both", expand=True)

        # --- header
        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="AudioBoost", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Normalize quiet video audio without clipping. Video is copied untouched.",
            style="Subtitle.TLabel",
            wraplength=WINDOW_WIDTH - 48,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # --- loudness target selector
        self._build_target_selector(container)

        # --- drop zone
        self._build_drop_zone(container)

        # --- selected file row (packs lazily)
        self.file_row = ttk.Frame(container)
        self.file_row.pack(fill="x", pady=(14, 0))
        self.file_label = ttk.Label(self.file_row, text="", style="File.TLabel")
        self.file_label.pack(side="left")
        self.clear_button = ttk.Button(
            self.file_row, text="Clear", command=self._clear_selection
        )

        # --- inline error (packs lazily)
        self.inline_error_var = tk.StringVar(value="")
        self.inline_error = ttk.Label(
            container, textvariable=self.inline_error_var, style="Error.TLabel"
        )

        # --- progress + status
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(
            container,
            mode="determinate",
            maximum=100,
            variable=self.progress_var,
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(18, 8))

        self.status_label = ttk.Label(container, text="", style="Muted.TLabel")
        self.status_label.pack(anchor="w")

        # --- action row pinned to the bottom
        action_row = ttk.Frame(container)
        action_row.pack(side="bottom", fill="x", pady=(16, 0))

        self.process_button = self._make_primary_button(
            action_row, "Boost Audio", self._on_process_clicked
        )
        self.process_button.pack(side="left")
        self._set_primary_enabled(False)

        self.cancel_button = ttk.Button(
            action_row, text="Cancel", command=self._on_cancel_clicked
        )
        self.show_button = ttk.Button(
            action_row, text="Show in Finder", command=self._on_show_in_finder
        )
        self.another_button = ttk.Button(
            action_row, text="Process another", command=self._reset_for_next
        )

        self._last_output: str | None = None

    # ---------- layout pieces ----------

    def _build_target_selector(self, parent: tk.Widget) -> None:
        p = self.palette
        section = ttk.Frame(parent)
        section.pack(fill="x", pady=(16, 0))
        ttk.Label(section, text="Loudness target", style="Muted.TLabel").pack(anchor="w")

        # The track wraps the three pills. aqua ignores bg on tk.Button when
        # relief is flat, so we use tk.Label (which always honors bg/fg) and
        # bind click ourselves.
        track = tk.Frame(
            section, bg=p.segment_track, highlightthickness=0, bd=0
        )
        track.pack(fill="x", pady=(8, 0), ipadx=3, ipady=3)

        last = len(TARGETS) - 1
        for idx, target in enumerate(TARGETS):
            text = f"{target.label}  {target.integrated_lufs:g}"
            seg = tk.Label(
                track,
                text=text,
                font=("SF Pro Text", 12, "bold"),
                bg=p.segment_bg,
                fg=p.segment_fg,
                padx=8,
                pady=7,
                cursor="hand2",
            )
            pad = (0, 0) if idx == last else (0, 3)
            seg.pack(side="left", expand=True, fill="both", padx=pad)
            seg.bind("<Button-1>", lambda _e, t=target: self._on_target_selected(t))
            self._segment_buttons[target] = seg

        self._apply_segment_styles()

    def _build_drop_zone(self, parent: tk.Widget) -> None:
        p = self.palette
        drop_wrap = ttk.Frame(parent)
        drop_wrap.pack(fill="x", pady=(18, 0))

        self.drop_frame = tk.Frame(
            drop_wrap,
            bg=p.drop_bg,
            highlightthickness=2,
            highlightbackground=p.drop_border,
            highlightcolor=p.drop_border,
            height=180,
            bd=0,
        )
        self.drop_frame.pack(fill="x")
        self.drop_frame.pack_propagate(False)

        drop_inner = tk.Frame(self.drop_frame, bg=p.drop_bg)
        drop_inner.pack(expand=True)

        # Waveform canvas: 11 rounded accent bars whose heights form a soft peak.
        self.wave_canvas = tk.Canvas(
            drop_inner,
            width=154,
            height=44,
            bg=p.drop_bg,
            highlightthickness=0,
            bd=0,
        )
        self.wave_canvas.pack(pady=(0, 10))
        self._paint_wave(p.accent)

        drop_primary = "Drop an MP4 here" if self._dnd_enabled else "Choose an MP4"
        self.drop_label = tk.Label(
            drop_inner,
            text=drop_primary,
            bg=p.drop_bg,
            fg=p.drop_text,
            font=("SF Pro Text", 15, "bold"),
            cursor="hand2",
        )
        self.drop_label.pack()

        drop_secondary = (
            "or click to choose a file" if self._dnd_enabled else "click to browse"
        )
        self.drop_hint = tk.Label(
            drop_inner,
            text=drop_secondary,
            bg=p.drop_bg,
            fg=p.drop_hint,
            font=("SF Pro Text", 11),
            cursor="hand2",
        )
        self.drop_hint.pack(pady=(2, 0))

        for widget in (
            self.drop_frame, drop_inner, self.wave_canvas,
            self.drop_label, self.drop_hint,
        ):
            widget.bind("<Button-1>", lambda _e: self._open_file_picker())

        if self._dnd_enabled:
            self.drop_frame.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropEnter>>", self._on_drop_enter)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<DropLeave>>", self._on_drop_leave)  # type: ignore[attr-defined]
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]

    _WAVE_HEIGHTS = (10, 18, 26, 34, 40, 44, 40, 34, 26, 18, 10)

    def _paint_wave(self, color: str) -> None:
        self.wave_canvas.delete("all")
        bar_w, gap = 8, 6
        total = len(self._WAVE_HEIGHTS) * bar_w + (len(self._WAVE_HEIGHTS) - 1) * gap
        x0 = (int(self.wave_canvas.cget("width")) - total) // 2
        canvas_h = int(self.wave_canvas.cget("height"))
        for i, h in enumerate(self._WAVE_HEIGHTS):
            x = x0 + i * (bar_w + gap)
            y_top = (canvas_h - h) // 2
            y_bot = y_top + h
            self.wave_canvas.create_rectangle(
                x, y_top, x + bar_w, y_bot,
                fill=color, outline=color,
            )

    # ---------- primary button (Label-based pill — aqua-proof) ----------

    def _make_primary_button(self, parent: tk.Widget, text: str, command) -> tk.Label:
        p = self.palette
        btn = tk.Label(
            parent,
            text=text,
            font=("SF Pro Text", 13, "bold"),
            bg=p.accent,
            fg=p.accent_fg,
            padx=22,
            pady=11,
            cursor="hand2",
        )
        btn.bind("<Button-1>", lambda _e: self._primary_click(command))
        btn.bind("<Enter>", lambda _e: self._hover_primary(True))
        btn.bind("<Leave>", lambda _e: self._hover_primary(False))
        return btn

    def _primary_click(self, command) -> None:
        if not self._primary_enabled:
            return
        p = self.palette
        # Brief press feedback, then fire.
        self.process_button.configure(bg=p.accent_hover)
        self.process_button.after(
            90, lambda: self.process_button.configure(bg=p.accent)
        )
        command()

    def _hover_primary(self, hovered: bool) -> None:
        if not self._primary_enabled:
            return
        p = self.palette
        self.process_button.configure(bg=p.accent_hover if hovered else p.accent)

    def _set_primary_enabled(self, enabled: bool) -> None:
        self._primary_enabled = enabled
        p = self.palette
        if enabled:
            self.process_button.configure(
                bg=p.accent, fg=p.accent_fg, cursor="hand2"
            )
        else:
            self.process_button.configure(
                bg=p.accent_disabled, fg=p.accent_disabled_fg, cursor="arrow"
            )

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
        if self._worker and self._worker.is_alive():
            return
        path = filedialog.askopenfilename(
            title="Choose an MP4",
            filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
        )
        if path:
            self._accept_file(path)

    def _paint_drop_zone(self, bg: str, border: str, wave_color: str) -> None:
        self.drop_frame.configure(
            bg=bg, highlightbackground=border, highlightcolor=border
        )
        for child in self.drop_frame.winfo_children():
            if isinstance(child, tk.Canvas):
                child.configure(bg=bg)
                continue
            try:
                child.configure(bg=bg)
            except tk.TclError:
                pass
            for sub in child.winfo_children():
                try:
                    sub.configure(bg=bg)
                except tk.TclError:
                    pass
        self._paint_wave(wave_color)

    def _on_drop_enter(self, _event) -> None:
        p = self.palette
        self._paint_drop_zone(p.drop_bg_active, p.accent, p.accent_hover)

    def _on_drop_leave(self, _event) -> None:
        p = self.palette
        self._paint_drop_zone(p.drop_bg, p.drop_border, p.accent)

    # ---------- target selector ----------

    def _on_target_selected(self, target: LoudnessTarget) -> None:
        if not self._segments_enabled:
            return
        if self._worker and self._worker.is_alive():
            return
        self._current_target = target
        self._apply_segment_styles()

    def _apply_segment_styles(self) -> None:
        p = self.palette
        for target, seg in self._segment_buttons.items():
            if target is self._current_target:
                seg.configure(bg=p.accent, fg=p.accent_fg)
            else:
                seg.configure(bg=p.segment_bg, fg=p.segment_fg)

    def _set_segments_enabled(self, enabled: bool) -> None:
        self._segments_enabled = enabled
        cursor = "hand2" if enabled else "arrow"
        for seg in self._segment_buttons.values():
            seg.configure(cursor=cursor)

    def _on_drop(self, event) -> None:
        self._on_drop_leave(event)
        paths = parse_dnd_paths(event.data)
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
            size_str = human_size(os.path.getsize(path))
        except OSError:
            size_str = "—"
        self.file_label.configure(text=f"{os.path.basename(path)}  ·  {size_str}")
        if not self.clear_button.winfo_ismapped():
            self.clear_button.pack(side="right")
        self._set_primary_enabled(True)

        self.progress_var.set(0.0)
        self.status_label.configure(text="Ready", style="Muted.TLabel")
        self._hide_completion_buttons()

    def _clear_selection(self) -> None:
        self._selected_path = None
        self.file_label.configure(text="")
        self.clear_button.pack_forget()
        self._set_primary_enabled(False)
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
        target = self._current_target
        self.status_label.configure(
            text=f"Starting… (target {target.integrated_lufs:g} LUFS)",
            style="Muted.TLabel",
        )
        self._set_primary_enabled(False)
        self._set_segments_enabled(False)
        self.cancel_button.pack(side="left", padx=(8, 0))

        self._processor = Processor()
        input_path = self._selected_path
        self._worker = threading.Thread(
            target=self._worker_main, args=(input_path, target), daemon=True
        )
        self._worker.start()

    def _on_cancel_clicked(self) -> None:
        if self._processor:
            self._processor.cancel()
        self.status_label.configure(text="Cancelling…", style="Muted.TLabel")
        self.cancel_button.configure(state="disabled")

    def _worker_main(self, input_path: str, target: LoudnessTarget) -> None:
        def progress_cb(label: str, pct: float) -> None:
            self.root.after(0, self._apply_progress, label, pct)

        assert self._processor is not None
        try:
            result = self._processor.process_file(input_path, progress_cb, target=target)
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
            self.root.after(0, self._on_processing_done, result.output_path, target)

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

    def _on_processing_done(self, output_path: str, target: LoudnessTarget) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(100.0)
        self._last_output = output_path
        self.status_label.configure(
            text=f"✓ Saved at {target.integrated_lufs:g} LUFS  ·  {os.path.basename(output_path)}",
            style="Success.TLabel",
        )
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self._set_segments_enabled(True)
        self._show_completion_buttons()

    def _on_processing_cancelled(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.status_label.configure(text="Cancelled", style="Muted.TLabel")
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self._set_segments_enabled(True)
        if self._selected_path:
            self._set_primary_enabled(True)

    def _on_processing_error(self, message: str, stderr_tail: str, show_details: bool) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self.status_label.configure(text="Failed", style="Error.TLabel")
        self._set_segments_enabled(True)
        if self._selected_path:
            self._set_primary_enabled(True)
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
        self._set_segments_enabled(True)
        if self._selected_path:
            self._set_primary_enabled(True)

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
            bg=self.palette.text_bg, fg=self.palette.text_fg,
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
