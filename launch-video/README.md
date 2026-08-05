# AudioBoost launch video

The [Remotion](https://remotion.dev) source for the launch video posted on
X/LinkedIn. The narration's before/after demo audio was processed by the
shipped AudioBoost.app itself.

## Render

```bash
npm i
npx remotion render Launch out/audioboost-launch.mp4
```

Preview with `npx remotion studio`.

## Regenerating the narration

Voice is Deepgram Aura-2 "aurora" via LiveKit Inference. Put your LiveKit
credentials in `.env` (gitignored — see `.env` keys in
`scripts/synth_livekit.py`), then:

```bash
set -a; source .env; set +a
python scripts/synth_livekit.py /tmp/vo_out
```

Degrade + boost the lines through the app (see the repo's commit history
for the exact pipeline), drop the wavs into `public/`, and update
`src/timings.json` with the measured durations — `src/timeline.ts` derives
every frame offset from it, so the video re-times itself.
