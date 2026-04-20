# AudioBoost

A native macOS drag-and-drop app that fixes quiet video audio without introducing
clipping or distortion. The video stream is copied losslessly; only the audio is
reprocessed and normalized to the YouTube loudness standard (-14 LUFS, -1.5 dBTP).

## Requirements

- macOS 11 or later
- [FFmpeg](https://ffmpeg.org) (install with Homebrew: `brew install ffmpeg`)

FFmpeg is not bundled with the app. AudioBoost detects it on PATH or at the standard
Homebrew locations (`/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`) and shows an
install prompt if it's missing.

## Install

1. Download `AudioBoost.app` (or build it — see below).
2. Drag it into `/Applications`.
3. The first time you launch it, **right-click → Open** to bypass Gatekeeper's
   "unidentified developer" warning. This is a one-time click; subsequent launches
   work normally.

## Usage

1. Launch AudioBoost.
2. Drag an `.mp4` onto the drop zone (or click it to choose a file).
3. Click **Boost Audio**.
4. The output appears next to the source as `<name>_boosted.mp4`. If that name is
   taken the app appends `_2`, `_3`, etc.

Click **Show in Finder** to reveal the result, or **Process another** to start over.

## What it does under the hood

AudioBoost runs a three-stage audio filter chain and copies the video stream
untouched:

1. `highpass=f=80` — strips sub-80 Hz rumble (mic handling, AC hum) before amplification.
2. `acompressor=threshold=-24dB:ratio=3:attack=20:release=250` — a gentle
   speech-friendly compressor that tames peaks so the loudness boost won't clip.
3. `loudnorm=I=-14:TP=-1.5:LRA=11` — EBU R128 loudness normalization. Run as a
   **two-pass** normalization: pass 1 measures the input, pass 2 applies linear
   (non-pumpy) correction using the measurements. Targets -14 LUFS integrated
   loudness with a -1.5 dBTP true-peak ceiling, which guarantees no digital
   clipping in the output.

The video stream is stream-copied (`-c:v copy`) — no re-encoding, no quality loss,
no visual changes. The MP4 `moov` atom is moved to the front (`-movflags +faststart`)
for instant playback.

## Run from source (local UI)

Requires Python 3.11+ with working `tkinter`. Homebrew's `python@3.12` and
`python@3.13` ship without Tk support — install the matching formula:

```bash
brew install python-tk@3.12     # or python-tk@3.13
```

macOS system Python 3.9 at `/usr/bin/python3` already bundles tkinter and also
works.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

The Tkinter window opens immediately — that's the UI. Drag any `.mp4` onto it.

### Quick smoke test with a synthesized file

If you don't have a quiet MP4 handy, generate one with FFmpeg and drop it on
the running window:

```bash
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" \
       -f lavfi -i "color=c=black:s=320x240:d=5" \
       -map 1:v -map 0:a -filter:a "volume=0.05" \
       -c:v libx264 -pix_fmt yuv420p -preset ultrafast \
       -c:a aac -b:a 128k -shortest /tmp/quiet.mp4
```

Drag `/tmp/quiet.mp4` onto the app, click **Boost Audio**, and
`/tmp/quiet_boosted.mp4` appears next to it. Verify the loudness landed near
-14 LUFS:

```bash
ffmpeg -i /tmp/quiet_boosted.mp4 \
       -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -
```

Look for `"input_i" : "-14.0x"` in the JSON block — that's the measured
integrated loudness of the output.

## Build the .app

```bash
./build_app.sh
```

This creates a virtualenv, installs dependencies, and produces
`dist/AudioBoost.app`. Override the interpreter with
`PYTHON_BIN=python3.12 ./build_app.sh`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and focused PRs welcome.

## License

[MIT](LICENSE) © 2026 Idris Olubisi

## Planned (not in v1)

- Configurable LUFS target (-14 / -16 / -23)
- ML-based noise removal (RNNoise / Demucs)
- Batch processing of multiple files
- Input formats beyond MP4 (MOV, MKV, WebM)
- Waveform preview before/after
- Finder Quick Action for right-click processing
- Bundled FFmpeg for zero-dependency install
