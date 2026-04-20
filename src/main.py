"""AudioBoost entry point."""

from __future__ import annotations

import os
import sys


def _ensure_src_on_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


def main() -> None:
    _ensure_src_on_path()
    from gui import run_app
    run_app()


if __name__ == "__main__":
    main()
