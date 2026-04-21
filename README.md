# AudioBoost

A native macOS drag-and-drop app that fixes quiet video audio without introducing
clipping or distortion. The video stream is copied losslessly when the codec is
MP4-compatible; only the audio is reprocessed and normalized to one of three
loudness presets (YouTube -14 LUFS, Podcast -16 LUFS, Broadcast/EBU R128 -23 LUFS).

Supports `.mp4`, `.mov`, `.mkv`, and `.webm` input. Output is always MP4.

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
2. (Optional) pick a loudness target: **YouTube -14**, **Podcast -16**, or
   **Broadcast -23**.
3. Drag an `.mp4`, `.mov`, `.mkv`, or `.webm` onto the drop zone (or click to
   choose a file).
4. Click **Boost Audio**.
5. The output appears next to the source as `<name>_boosted.mp4`. If that name is
   taken the app appends `_2`, `_3`, etc.

Click **Show in Finder** to reveal the result, or **Process another** to start over.

### Headless mode (CLI)

AudioBoost can process files without opening a window — useful for scripts,
cron jobs, or the Finder Quick Action below. Invoke the bundled binary
directly:

```bash
/Applications/AudioBoost.app/Contents/MacOS/AudioBoost \
  --cli --target podcast path/to/video.mp4
```

Flags:

- `--cli` — no GUI; process the given files and exit.
- `--target {youtube,podcast,broadcast}` — loudness preset (default
  `youtube`).
- positional `FILE`s — any number of input videos. Each produces
  `<name>_boosted.mp4` next to the source.

A macOS notification is posted when processing starts and again when it
finishes. The process prints per-file progress to stdout and exits 0 on
success, non-zero on any failure.

### Right-click in Finder (Quick Action)

Install the Quick Action once to get a **Boost Audio with AudioBoost** item
in Finder's right-click menu:

```bash
./quick_action/install.sh
```

Then right-click any `.mp4` / `.mov` / `.mkv` / `.webm` file → **Quick
Actions** → **Boost Audio with AudioBoost**. The workflow wraps the CLI
above, so notifications appear and the output lands next to the source.

Uninstall with `./quick_action/install.sh --uninstall`.

## What it does under the hood

AudioBoost runs a three-stage audio filter chain:

1. `highpass=f=80` — strips sub-80 Hz rumble (mic handling, AC hum) before amplification.
2. `acompressor=threshold=-24dB:ratio=3:attack=20:release=250` — a gentle
   speech-friendly compressor that tames peaks so the loudness boost won't clip.
3. `loudnorm=I=<target>:TP=<peak>:LRA=<range>` — EBU R128 loudness normalization.
   Run as a **two-pass** normalization: pass 1 measures the input, pass 2 applies
   linear (non-pumpy) correction using the measurements. True-peak ceiling
   (-1.5 dBTP for YouTube/Podcast, -1.0 for Broadcast) guarantees no digital
   clipping in the output.

**Video:** if the source codec can live in an MP4 container (H.264, H.265/HEVC,
AV1, MPEG-4), the video stream is passed through with `-c:v copy` — no
re-encoding, no quality loss. For codecs that can't (VP8, VP9, ProRes, DNxHD,
etc. — typical in WebM and some MOV/MKV files) AudioBoost re-encodes to H.264
at CRF 18 with the `slow` preset, which is visually near-lossless but slower
than passthrough. The status line indicates which path is running.

The MP4 `moov` atom is moved to the front (`-movflags +faststart`) for instant
playback.

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

## Planned

- ML-based noise removal (RNNoise / Demucs)
- Batch processing of multiple files (CLI already supports multi-file)
- Waveform preview before/after
- Bundled FFmpeg for zero-dependency install
