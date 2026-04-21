"""AudioBoost entry point. GUI by default, headless with --cli."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Optional


CLI_TARGETS = {
    "youtube": "TARGET_YOUTUBE",
    "podcast": "TARGET_PODCAST",
    "broadcast": "TARGET_BROADCAST",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="AudioBoost",
        description=(
            "Boost quiet video audio to a chosen loudness target. "
            "With no flags, opens the GUI. With --cli, processes the given "
            "files headlessly and posts a macOS notification when done."
        ),
    )
    parser.add_argument(
        "--cli", action="store_true",
        help="Run headless; no GUI.",
    )
    parser.add_argument(
        "--target",
        choices=list(CLI_TARGETS.keys()),
        default="youtube",
        help="Loudness preset (default: youtube / -14 LUFS).",
    )
    parser.add_argument(
        "files", nargs="*", metavar="FILE",
        help=(
            "Video file(s) to boost. In --cli mode each is processed in turn. "
            "Without --cli the first file is preloaded in the GUI."
        ),
    )
    return parser.parse_args(argv)


def _post_notification(title: str, message: str) -> None:
    """Post a macOS notification via osascript. Silent failure if unavailable."""
    script = f'display notification {_as_applescript_string(message)} ' \
             f'with title {_as_applescript_string(title)}'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False, capture_output=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _as_applescript_string(value: str) -> str:
    """Quote a string for safe interpolation into AppleScript source."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _run_cli(files: list[str], target_name: str) -> int:
    import processor
    target = getattr(processor, CLI_TARGETS[target_name])

    if not files:
        print("audioboost --cli: no files given", file=sys.stderr)
        return 2

    _post_notification(
        "AudioBoost",
        f"Processing {len(files)} file(s) at {target.integrated_lufs:g} LUFS…",
    )

    exit_code = 0
    outputs: list[str] = []
    for path in files:
        if not os.path.isfile(path):
            print(f"  skip: not a file: {path}", file=sys.stderr)
            exit_code = 1
            continue

        last_reported = -10.0

        def cb(label: str, pct: float, _path: str = path) -> None:
            nonlocal last_reported
            if pct >= 0 and pct - last_reported >= 10:
                print(f"  {os.path.basename(_path)}: {label} {pct:.0f}%")
                last_reported = pct

        try:
            result = processor.process_file(path, cb, target=target)
            outputs.append(result.output_path)
            print(f"  ✓ {os.path.basename(result.output_path)}")
        except processor.ProcessingError as exc:
            print(f"  ✗ {os.path.basename(path)}: {exc}", file=sys.stderr)
            exit_code = 1
        except processor.FFmpegNotFoundError as exc:
            print(f"  ✗ ffmpeg not found: {exc}", file=sys.stderr)
            exit_code = 1
        except Exception as exc:  # pragma: no cover - defensive catch-all
            print(f"  ✗ {os.path.basename(path)}: {exc}", file=sys.stderr)
            exit_code = 1

    if outputs:
        if len(outputs) == 1:
            msg = f"Saved {os.path.basename(outputs[0])}"
        else:
            msg = f"Saved {len(outputs)} files"
        _post_notification("AudioBoost done", msg)
    elif exit_code != 0:
        _post_notification("AudioBoost failed", "No files produced. Check terminal.")

    return exit_code


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.cli:
        return _run_cli(args.files, args.target)

    from gui import run_app
    initial_file = args.files[0] if args.files else None
    run_app(initial_file=initial_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
