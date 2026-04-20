# Contributing to AudioBoost

Contributions are welcome. AudioBoost is small on purpose — a focused desktop
utility for boosting quiet screen-recording audio. The goal is to keep it that
way.

## Ground rules

- Keep dependencies minimal. Python stdlib + `tkinterdnd2` + `py2app` is the
  whole surface area today; new runtime deps need a strong justification.
- Don't re-encode video. Any change must preserve `-c:v copy` behavior. The
  acceptance test is a bit-identical video-stream MD5 before and after.
- Don't ship an output that can clip. Keep the -1.5 dBTP ceiling in place.
- No telemetry, no network calls, no cloud services.

## Dev setup

Requires macOS and FFmpeg (`brew install ffmpeg`) plus a Python with tkinter.
If you use Homebrew Python, also install the matching Tk formula:

```bash
brew install python-tk@3.12   # or @3.13
```

Then:

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

## What I'll gladly review

- Bug fixes with a reproducer
- Better error messages for edge-case FFmpeg failures
- Cross-Python-version compatibility fixes (3.11–3.13)
- Accessibility improvements in the GUI
- Items from the "Planned" list in the README

## What will probably get closed

- Changes that add a configuration option for something nobody asked for
- Rewrites into a different GUI framework
- Bundling a custom FFmpeg build (licensing overhead, not worth it)
- Scope creep into general audio/video editing

## Filing a bug

Open an issue with:

1. macOS version, Python version, FFmpeg version (`ffmpeg -version | head -1`)
2. Steps to reproduce, including a short sample file if possible
3. The exact error text (the "Copy error" button in the error dialog helps)

## Pull requests

- One logical change per PR
- Run your change against a real screen recording before submitting
- For audio-path changes, include a before/after `loudnorm` measurement in the
  PR description (`ffmpeg -i out.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -`)

## License

By submitting a PR you agree that your contribution is licensed under the MIT
License (see [LICENSE](LICENSE)).
