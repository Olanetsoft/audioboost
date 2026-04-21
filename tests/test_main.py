"""Tests for main.py — argparse surface and the --cli code path."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from tests import _setup  # noqa: F401  (puts src/ on sys.path)

import main
import processor


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


class ParseArgsTest(unittest.TestCase):
    def test_no_flags_means_gui(self):
        args = main._parse_args([])
        self.assertFalse(args.cli)
        self.assertEqual(args.target, "youtube")
        self.assertEqual(args.files, [])

    def test_cli_flag_sets_cli(self):
        args = main._parse_args(["--cli"])
        self.assertTrue(args.cli)

    def test_target_choices(self):
        for name in ("youtube", "podcast", "broadcast"):
            args = main._parse_args(["--cli", "--target", name])
            self.assertEqual(args.target, name)

    def test_unknown_target_fails(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                main._parse_args(["--cli", "--target", "bogus"])

    def test_files_are_collected(self):
        args = main._parse_args(["--cli", "a.mp4", "b.mp4"])
        self.assertEqual(args.files, ["a.mp4", "b.mp4"])

    def test_gui_mode_can_take_initial_file(self):
        args = main._parse_args(["video.mp4"])
        self.assertFalse(args.cli)
        self.assertEqual(args.files, ["video.mp4"])

    def test_target_defaults_to_youtube(self):
        args = main._parse_args(["--cli", "x.mp4"])
        self.assertEqual(args.target, "youtube")

    def test_cli_targets_mapping_covers_all_presets(self):
        # Every preset in the mapping must resolve to an exported target.
        for name, attr in main.CLI_TARGETS.items():
            self.assertTrue(hasattr(processor, attr), name)


# ---------------------------------------------------------------------------
# AppleScript string quoting
# ---------------------------------------------------------------------------


class AppleScriptQuotingTest(unittest.TestCase):
    def test_plain_string_gets_quoted(self):
        self.assertEqual(main._as_applescript_string("hello"), '"hello"')

    def test_double_quote_is_escaped(self):
        self.assertEqual(main._as_applescript_string('a"b'), '"a\\"b"')

    def test_backslash_is_escaped_first(self):
        self.assertEqual(main._as_applescript_string("a\\b"), '"a\\\\b"')

    def test_combined_backslash_and_quote(self):
        self.assertEqual(
            main._as_applescript_string('x\\"y'),
            '"x\\\\\\"y"',
        )


# ---------------------------------------------------------------------------
# CLI run path
# ---------------------------------------------------------------------------


class RunCliTest(unittest.TestCase):
    def setUp(self) -> None:
        # osascript is invoked for notifications; stub it out so the test
        # doesn't pop notifications during the suite.
        self._notify_patch = patch("main._post_notification")
        self._notify = self._notify_patch.start()
        self.addCleanup(self._notify_patch.stop)

    def test_empty_files_returns_exit_code_two(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main._run_cli([], "youtube"), 2)

    def test_missing_file_is_reported_and_returns_nonzero(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = main._run_cli(["/nonexistent/path.mp4"], "youtube")
        self.assertEqual(rc, 1)
        self.assertIn("not a file", err.getvalue())

    def test_happy_path_calls_processor_with_correct_target(self):
        result = processor.ProcessResult(output_path="/tmp/x_boosted.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.mp4")
            open(src, "w").close()

            with patch("processor.process_file",
                       return_value=result) as pf, \
                 redirect_stdout(io.StringIO()):
                rc = main._run_cli([src], "podcast")

            self.assertEqual(rc, 0)
            pf.assert_called_once()
            _, kwargs = pf.call_args
            self.assertIs(kwargs["target"], processor.TARGET_PODCAST)

    def test_notification_posted_on_success(self):
        result = processor.ProcessResult(output_path="/tmp/x_boosted.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.mp4")
            open(src, "w").close()
            with patch("processor.process_file", return_value=result), \
                 redirect_stdout(io.StringIO()):
                main._run_cli([src], "youtube")

        # Start + done notification.
        self.assertEqual(self._notify.call_count, 2)
        titles = [call.args[0] for call in self._notify.call_args_list]
        self.assertEqual(titles[-1], "AudioBoost done")

    def test_processing_error_returns_nonzero_but_continues(self):
        """If one file fails, the CLI reports it but still tries the rest."""
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "good.mp4")
            bad = os.path.join(tmp, "bad.mp4")
            open(good, "w").close()
            open(bad, "w").close()

            call_count = {"n": 0}

            def pf_side_effect(path, cb=None, *, target):
                call_count["n"] += 1
                if path == bad:
                    raise processor.ProcessingError("boom", stderr_tail="")
                return processor.ProcessResult(output_path=path + "_boosted.mp4")

            with patch("processor.process_file", side_effect=pf_side_effect), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = main._run_cli([good, bad], "youtube")

            self.assertEqual(rc, 1)
            self.assertEqual(call_count["n"], 2, "both files must be attempted")

    def test_ffmpeg_not_found_reported_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.mp4")
            open(src, "w").close()
            with patch("processor.process_file",
                       side_effect=processor.FFmpegNotFoundError("missing")), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                rc = main._run_cli([src], "youtube")
            self.assertEqual(rc, 1)
            self.assertIn("ffmpeg not found", err.getvalue())


# ---------------------------------------------------------------------------
# main() dispatch
# ---------------------------------------------------------------------------


class MainDispatchTest(unittest.TestCase):
    def test_main_dispatches_to_cli_when_flag_set(self):
        with patch("main._run_cli", return_value=0) as run_cli:
            rc = main.main(["--cli", "x.mp4"])
        run_cli.assert_called_once_with(["x.mp4"], "youtube")
        self.assertEqual(rc, 0)

    def test_main_dispatches_to_gui_by_default(self):
        fake_run_app = MagicMock()
        fake_gui = MagicMock(run_app=fake_run_app)
        with patch.dict("sys.modules", {"gui": fake_gui}):
            rc = main.main([])
        fake_run_app.assert_called_once_with(initial_file=None)
        self.assertEqual(rc, 0)

    def test_main_passes_first_file_as_initial_to_gui(self):
        fake_run_app = MagicMock()
        fake_gui = MagicMock(run_app=fake_run_app)
        with patch.dict("sys.modules", {"gui": fake_gui}):
            main.main(["a.mp4", "b.mp4"])
        fake_run_app.assert_called_once_with(initial_file="a.mp4")


if __name__ == "__main__":
    unittest.main()
