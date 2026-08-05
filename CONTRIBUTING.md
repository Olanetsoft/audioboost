# Contributing to AudioBoost

Contributions are welcome. AudioBoost is small on purpose — a focused desktop
utility for boosting quiet screen-recording audio. The goal is to keep it that
way.

## Ground rules

- Keep dependencies minimal. Python stdlib + `pywebview` + `py2app` is the
  whole surface area today; new runtime deps need a strong justification.
- Don't re-encode video. Any change must preserve `-c:v copy` behavior. The
  acceptance test is a bit-identical video-stream MD5 before and after.
- Don't ship an output that can clip. Keep the -1.5 dBTP ceiling in place.
- No telemetry, no network calls, no cloud services.

## Dev setup

Requires macOS, FFmpeg (`brew install ffmpeg`), and Python 3.11+.

```bash
git clone https://github.com/Olanetsoft/audioboost.git
cd audioboost
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Building the .app locally

```bash
./build_app.sh
open dist/AudioBoost.app
```

## Running tests

The test suite uses `unittest` from the standard library — no extra deps.
Run it from the repo root:

```bash
python3 -m unittest discover tests -v
```

The suite is in six modules:

- [`tests/test_ffmpeg_utils.py`](tests/test_ffmpeg_utils.py) — binary
  discovery (bundled → PATH → Homebrew), file probing, loudnorm-JSON /
  progress-line parsing, waveform argv builder.
- [`tests/test_processor.py`](tests/test_processor.py) — `LoudnessTarget`
  presets, output-path collision handling, filter-chain assembly (via
  mocked `subprocess.Popen` — asserts exact ffmpeg args for both passes,
  copy vs re-encode branches), error wrapping, cancellation.
- [`tests/test_app_core.py`](tests/test_app_core.py) — the headless core
  behind the GUI: snapshot shape, queue add/dedupe/reject, target
  persistence, and the real batch flow against ffmpeg (done +
  failure-continues + waveform data URIs).
- [`tests/test_main.py`](tests/test_main.py) — CLI argument surface and
  the `--cli` batch path.
- [`tests/test_integration.py`](tests/test_integration.py) — real ffmpeg
  end-to-end: loudness within ±0.5 LU of each preset, bit-identical
  video stream, VP9→H.264 re-encode, cancel cleanup. Auto-skipped if
  ffmpeg isn't available.
- [`tests/test_gui_helpers.py`](tests/test_gui_helpers.py) —
  `human_size`, settings persistence, queue-item model, batch summary.

If you change any of these files, add a test. In particular: any change
to the audio filter chain must come with updated assertions in
`FilterChainAssemblyTest` (and, if it's not a mocks-only refactor, a new
integration test).

## What I'll gladly review

- Bug fixes with a reproducer
- Better error messages for edge-case FFmpeg failures
- Cross-Python-version compatibility fixes (3.11–3.13)
- Accessibility improvements in the GUI
- Items from the "Planned" list in the README

## What will probably get closed

- Changes that add a configuration option for something nobody asked for
- Rewrites into a different GUI framework
- Swapping the pinned static FFmpeg source for a custom-compiled build
- Scope creep into general audio/video editing

## Filing a bug

Open an issue with:

1. macOS version, Python version, FFmpeg version (`ffmpeg -version | head -1`)
2. Steps to reproduce, including a short sample file if possible
3. The exact error text (the app's "ffmpeg output" panel under a failed
   item is selectable)

## Pull requests

- One logical change per PR
- Run your change against a real screen recording before submitting
- For audio-path changes, include a before/after `loudnorm` measurement in the
  PR description (`ffmpeg -i out.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -`)

## License

By submitting a PR you agree that your contribution is licensed under the MIT
License (see [LICENSE](LICENSE)).
