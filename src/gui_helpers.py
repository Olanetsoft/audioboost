"""UI-toolkit-free helpers shared by the app core and tests."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


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


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------


def settings_path() -> str:
    return os.path.expanduser(
        "~/Library/Application Support/AudioBoost/settings.json"
    )


def load_settings(path: str | None = None) -> dict:
    """Read settings; any missing/corrupt/foreign content degrades to {}."""
    try:
        with open(path or settings_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict, path: str | None = None) -> None:
    """Write settings atomically; failures are silent (settings are optional)."""
    target = path or settings_path()
    tmp = target + ".tmp"
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, target)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Batch queue model
# ---------------------------------------------------------------------------


# Status values for QueueItem. Using string constants (not an enum) so the
# values read naturally in logs, snapshots, and test assertions.
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass
class QueueItem:
    """One entry in the batch queue."""

    path: str
    size_bytes: int
    status: str = STATUS_PENDING
    output_path: str | None = None
    error_message: str | None = None
    # Pass-1 analysis cache: the loudnorm measurement dict, the target label
    # it was measured against (offset is target-specific), and the input
    # loudness parsed out for display.
    measured: dict | None = None
    measured_target: str | None = None
    measured_lufs: float | None = None

    @property
    def basename(self) -> str:
        return os.path.basename(self.path)


def summarize_completion(items: list[QueueItem]) -> str:
    """Label shown after a batch finishes."""
    done = sum(1 for i in items if i.status == STATUS_DONE)
    failed = sum(1 for i in items if i.status == STATUS_FAILED)
    if failed == 0 and done > 0:
        return f"✓ Saved {done} file{'s' if done != 1 else ''}"
    if done == 0 and failed > 0:
        return f"Failed: {failed} file{'s' if failed != 1 else ''}"
    return f"Done: {done} saved · {failed} failed"
