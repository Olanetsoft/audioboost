"""Tk-free helpers used by the GUI.

Extracted so they can be unit-tested without loading tkinter, which would
otherwise pull in a real Tk runtime on import.
"""

from __future__ import annotations

import subprocess


def human_size(nbytes: int) -> str:
    """Format a byte count as a short human-readable string."""
    value: float = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def parse_dnd_paths(data: str) -> list[str]:
    """Split the tkdnd `<<Drop>>` event data into individual file paths.

    tkdnd delivers file lists as space-separated, with braces wrapping any
    path containing spaces — e.g. ``"/tmp/a.mp4 {/tmp/b c.mp4}"``.
    """
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


def is_dark_mode() -> bool:
    """Return True if macOS is currently in Dark Mode.

    macOS writes 'Dark' to the global AppleInterfaceStyle default in dark
    mode and removes the key entirely in light mode (so `defaults read`
    exits non-zero).
    """
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=1,
        )
        return result.returncode == 0 and result.stdout.strip() == "Dark"
    except (OSError, subprocess.TimeoutExpired):
        return False


class Palette:
    """Colors chosen to match macOS light/dark panels, plus an indigo accent
    used for the primary action, selected segments, drop-zone hover, and the
    waveform glyph. ttk widgets remain unstyled for backgrounds so they keep
    their native aqua rendering."""

    _REQUIRED_ATTRS = (
        "drop_bg", "drop_bg_active", "drop_border",
        "drop_text", "drop_hint",
        "muted", "error", "success",
        "text_bg", "text_fg",
        "segment_track", "segment_bg", "segment_fg",
        "accent", "accent_hover", "accent_fg",
        "accent_disabled", "accent_disabled_fg",
    )

    def __init__(self, dark: bool) -> None:
        self.dark = dark
        if dark:
            self.drop_bg = "#1f1f23"
            self.drop_bg_active = "#232744"
            self.drop_border = "#2e2e33"
            self.drop_text = "#f3f4f6"
            self.drop_hint = "#9ca3af"
            self.muted = "#9ca3af"
            self.error = "#f87171"
            self.success = "#4ade80"
            self.text_bg = "#111114"
            self.text_fg = "#e5e7eb"
            self.segment_track = "#1a1a1d"
            self.segment_bg = "#2c2c30"
            self.segment_fg = "#e5e7eb"
            self.accent = "#818cf8"
            self.accent_hover = "#6366f1"
            self.accent_fg = "#ffffff"
            self.accent_disabled = "#3f3f46"
            self.accent_disabled_fg = "#9ca3af"
        else:
            self.drop_bg = "#ffffff"
            self.drop_bg_active = "#eef0ff"
            self.drop_border = "#e5e7eb"
            self.drop_text = "#111827"
            self.drop_hint = "#6b7280"
            self.muted = "#6b7280"
            self.error = "#b91c1c"
            self.success = "#15803d"
            self.text_bg = "#fafafa"
            self.text_fg = "#111827"
            self.segment_track = "#e5e7eb"
            self.segment_bg = "#ffffff"
            self.segment_fg = "#4b5563"
            self.accent = "#6366f1"
            self.accent_hover = "#4f46e5"
            self.accent_fg = "#ffffff"
            self.accent_disabled = "#c7d2fe"
            self.accent_disabled_fg = "#ffffff"
