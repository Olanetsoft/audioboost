"""Synthesize the launch-video narration via LiveKit Inference TTS.

Reads LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET from the
environment (source launch-video/.env). Writes raw lines to the output
directory given as argv[1].

Usage:
    set -a; source .env; set +a
    python scripts/synth_livekit.py /tmp/abvideo4
"""

from __future__ import annotations

import asyncio
import os
import sys
import wave

import aiohttp
from livekit.agents import inference

VOICE_MODEL = "deepgram/aura-2"
VOICE = "aurora"

LINES = {
    "announce": "Announcing AudioBoost — a tiny Mac app that fixes quiet video audio.",
    "problem": "You know the pain. You finish a screen recording, and the mic was way too low. Listen to this.",
    "quiet_src": "This is a screen recording where my mic was way too quiet.",
    "reveal": "Now — the same recording, after one drop into AudioBoost.",
    "explain": "Two-pass loudness normalization to minus fourteen L U F S. No clipping. And your video stream? Untouched.",
    "f1": "Every format. MP4, MOV, MKV, WebM.",
    "f2": "Batch a whole folder at once.",
    "f3": "Three loudness targets. YouTube, Podcast, Broadcast.",
    "f4": "Before and after waveforms.",
    "f5": "FFmpeg built in. Zero setup.",
    "f6": "Even right-click, straight from Finder.",
    "cta": "AudioBoost. Free and open source. Grab it on GitHub.",
}


async def synth_line(tts: inference.TTS, name: str, text: str, outdir: str) -> None:
    frames = []
    stream = tts.synthesize(text)
    async for ev in stream:
        frames.append(ev.frame)
    if not frames:
        raise RuntimeError(f"no audio for {name}")
    path = os.path.join(outdir, f"{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(frames[0].num_channels)
        w.setsampwidth(2)
        w.setframerate(frames[0].sample_rate)
        for f in frames:
            w.writeframes(bytes(f.data))
    dur = sum(f.samples_per_channel for f in frames) / frames[0].sample_rate
    print(f"  {name}.wav  {dur:.2f}s")


async def main(outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    # Standalone use (no agent worker) requires an explicit HTTP session.
    async with aiohttp.ClientSession() as session:
        tts = inference.TTS(model=VOICE_MODEL, voice=VOICE, http_session=session)
        try:
            for name, text in LINES.items():
                await synth_line(tts, name, text, outdir)
        finally:
            await tts.aclose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: synth_livekit.py <outdir>")
    asyncio.run(main(sys.argv[1]))
