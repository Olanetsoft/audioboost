"""FFmpeg detection, probing, and output parsing."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass


class FFmpegNotFoundError(RuntimeError):
    """FFmpeg binary could not be located on this system."""


class FFprobeError(RuntimeError):
    """ffprobe failed to read the input file."""


_HOMEBREW_CANDIDATES = (
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
)


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    for candidate in _HOMEBREW_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FFmpegNotFoundError("ffmpeg not found on PATH or in Homebrew locations")


def find_ffprobe() -> str:
    ffmpeg_path = find_ffmpeg()
    sibling = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
    if os.path.isfile(sibling) and os.access(sibling, os.X_OK):
        return sibling
    path = shutil.which("ffprobe")
    if path:
        return path
    raise FFmpegNotFoundError("ffprobe not found alongside ffmpeg")


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: float
    has_audio: bool


def probe_file(path: str) -> ProbeResult:
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type",
        "-of", "json",
        path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )
    except subprocess.CalledProcessError as exc:
        raise FFprobeError(exc.stderr.strip() or "ffprobe failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFprobeError("ffprobe timed out") from exc

    data = json.loads(result.stdout or "{}")
    fmt = data.get("format", {})
    duration_str = fmt.get("duration")
    try:
        duration = float(duration_str) if duration_str is not None else 0.0
    except (TypeError, ValueError):
        duration = 0.0

    streams = data.get("streams", []) or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return ProbeResult(duration_seconds=duration, has_audio=has_audio)


_LOUDNORM_JSON_RE = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.DOTALL)


def _clamp_numeric(value: str, fallback: float) -> str:
    """Replace non-finite numeric strings (-inf, inf, nan) with a fallback."""
    cleaned = value.strip().lower()
    if cleaned in {"-inf", "inf", "+inf", "nan", "-nan"}:
        return f"{fallback:.2f}"
    try:
        float(value)
        return value
    except (TypeError, ValueError):
        return f"{fallback:.2f}"


def parse_loudnorm_json(stderr_text: str) -> dict:
    """Extract and sanitize the JSON block emitted by FFmpeg's loudnorm filter."""
    match = _LOUDNORM_JSON_RE.search(stderr_text)
    if not match:
        raise ValueError("Could not find loudnorm JSON block in ffmpeg output")
    raw = json.loads(match.group(0))

    return {
        "input_i": _clamp_numeric(raw.get("input_i", "-70"), -70.0),
        "input_tp": _clamp_numeric(raw.get("input_tp", "-70"), -70.0),
        "input_lra": _clamp_numeric(raw.get("input_lra", "0"), 0.0),
        "input_thresh": _clamp_numeric(raw.get("input_thresh", "-70"), -70.0),
        "target_offset": _clamp_numeric(raw.get("target_offset", "0"), 0.0),
    }


def parse_progress_line(line: str) -> tuple[str, str] | None:
    """Parse a `key=value` line from `ffmpeg -progress pipe:1`. Returns None on non-kv lines."""
    line = line.strip()
    if not line or "=" not in line:
        return None
    key, _, value = line.partition("=")
    return key.strip(), value.strip()
