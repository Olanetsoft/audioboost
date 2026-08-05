"""pywebview shell around AppCore: window, JS bridge, macOS open events."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import webview

from app_core import AppCore

WINDOW_WIDTH = 600
WINDOW_HEIGHT = 780


def _index_html_path() -> str:
    resources = os.environ.get("RESOURCEPATH")  # py2app bundle
    if resources:
        candidate = os.path.join(resources, "web", "index.html")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "web", "index.html")


class Api:
    """Methods callable from JS via window.pywebview.api.*"""

    def __init__(self, core: AppCore) -> None:
        self._core = core
        self.window: webview.Window | None = None

    # -- state --
    def get_state(self) -> dict:
        return self._core.snapshot()

    # -- queue --
    def add_files(self, paths: list[str]) -> None:
        self._core.add_files(paths)

    def browse(self) -> None:
        if self.window is None:
            return
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=("Video files (*.mp4;*.mov;*.mkv;*.webm;*.m4v)",
                        "All files (*.*)"),
        )
        if result:
            self._core.add_files(list(result))

    def clear(self) -> None:
        self._core.clear()

    # -- processing --
    def set_target(self, label: str) -> None:
        self._core.set_target(label)

    def start(self) -> None:
        self._core.start()

    def cancel(self) -> None:
        self._core.cancel()

    # -- shell --
    def show_in_finder(self) -> None:
        self._core.show_in_finder()

    def copy_text(self, text: str) -> None:
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=False)
        except OSError:
            pass


def _register_open_document_handler(core: AppCore) -> None:
    """Route macOS open-document Apple Events (Dock drop, Open With,
    `open -a AudioBoost file.mp4`) into the queue. Best-effort: pywebview's
    macOS backend runs on PyObjC, so AppKit is importable inside the app."""
    try:
        import objc  # noqa: F401
        from Foundation import NSObject, NSAppleEventManager, NSURL

        kCoreEventClass = 0x61657674  # 'aevt'
        kAEOpenDocuments = 0x6F646F63  # 'odoc'
        keyDirectObject = 0x2D2D2D2D  # '----'

        class _OpenDocHandler(NSObject):
            def handleOpenEvent_withReplyEvent_(self, event, _reply):
                paths = []
                direct = event.paramDescriptorForKeyword_(keyDirectObject)
                if direct is not None:
                    for i in range(1, direct.numberOfItems() + 1):
                        item = direct.descriptorAtIndex_(i)
                        url_str = item.stringValue()
                        if not url_str:
                            continue
                        url = NSURL.URLWithString_(url_str)
                        if url is not None and url.isFileURL():
                            paths.append(url.path())
                if paths:
                    core.add_files(paths)

        handler = _OpenDocHandler.alloc().init()
        NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
            handler, b"handleOpenEvent:withReplyEvent:",
            kCoreEventClass, kAEOpenDocuments,
        )
        # Keep the handler alive for the process lifetime.
        _register_open_document_handler._handler = handler  # type: ignore[attr-defined]
    except Exception:
        pass


def run_app(initial_file: str | None = None) -> None:
    core = AppCore()
    api = Api(core)

    window = webview.create_window(
        "AudioBoost",
        url=_index_html_path(),
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(WINDOW_WIDTH, WINDOW_HEIGHT),
        resizable=True,
        background_color="#0b0f0e",
    )
    api.window = window

    def push(snapshot: dict) -> None:
        try:
            window.evaluate_js(f"AB.push({json.dumps(snapshot)})")
        except Exception:
            pass  # window not ready / closing

    core._push_cb = push

    # pywebview >= 5 exposes dropped files' full paths to the DOM.
    try:
        webview.settings["ALLOW_FILE_DROP"] = True
    except Exception:
        pass

    def on_start() -> None:
        _register_open_document_handler(core)
        if initial_file:
            core.add_files([initial_file])

    webview.start(on_start, debug=os.environ.get("AUDIOBOOST_DEBUG") == "1")


if __name__ == "__main__":
    run_app(sys.argv[1] if len(sys.argv) > 1 else None)
