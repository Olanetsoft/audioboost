import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio } from "@remotion/media";
import { SceneFade } from "./components/SceneFade";
import { Hook } from "./scenes/Hook";
import { Problem } from "./scenes/Problem";
import { Boost } from "./scenes/Boost";
import { AppShot } from "./scenes/AppShot";
import { Features } from "./scenes/Features";
import { Outro } from "./scenes/Outro";
import { T } from "./theme";
import {
  ANNOUNCE_AT,
  APP_START,
  BOOSTED_AT,
  BOOST_START,
  CTA_AT,
  EXPLAIN_AT,
  FEATURES_START,
  FEATURE_ATS,
  HOOK_START,
  OUTRO_START,
  PROBLEM_AT,
  PROBLEM_START,
  QUIET_AT,
  REVEAL_AT,
  TOTAL_FRAMES,
} from "./timeline";

export { TOTAL_FRAMES };

const Grain: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundImage:
        "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")",
      opacity: 0.04,
      pointerEvents: "none",
    }}
  />
);

export const Launch: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: T.bg, fontFamily: T.ui }}>
      {/* scenes — each cross-fades at its edges */}
      <Sequence from={HOOK_START} durationInFrames={PROBLEM_START - HOOK_START} name="Hook">
        <SceneFade dur={PROBLEM_START - HOOK_START}>
          <Hook />
        </SceneFade>
      </Sequence>
      <Sequence from={PROBLEM_START} durationInFrames={BOOST_START - PROBLEM_START} name="Problem">
        <SceneFade dur={BOOST_START - PROBLEM_START}>
          <Problem listenFrom={QUIET_AT - PROBLEM_START} />
        </SceneFade>
      </Sequence>
      <Sequence from={BOOST_START} durationInFrames={APP_START - BOOST_START} name="Boost">
        <SceneFade dur={APP_START - BOOST_START}>
          <Boost sweepFrom={BOOSTED_AT - BOOST_START} />
        </SceneFade>
      </Sequence>
      <Sequence from={APP_START} durationInFrames={FEATURES_START - APP_START} name="AppShot">
        <SceneFade dur={FEATURES_START - APP_START}>
          <AppShot />
        </SceneFade>
      </Sequence>
      <Sequence from={FEATURES_START} durationInFrames={OUTRO_START - FEATURES_START} name="Features">
        <SceneFade dur={OUTRO_START - FEATURES_START}>
          <Features rowAts={FEATURE_ATS.map((f) => f - FEATURES_START)} />
        </SceneFade>
      </Sequence>
      <Sequence from={OUTRO_START} durationInFrames={TOTAL_FRAMES - OUTRO_START} name="Outro">
        <SceneFade dur={TOTAL_FRAMES - OUTRO_START}>
          <Outro />
        </SceneFade>
      </Sequence>

      {/* narration — offsets derived from measured durations (timeline.ts) */}
      <Audio src={staticFile("vo_announce.wav")} from={ANNOUNCE_AT} name="VO announce" />
      <Audio src={staticFile("vo_problem.wav")} from={PROBLEM_AT} name="VO problem" />
      <Audio src={staticFile("quiet.wav")} from={QUIET_AT} name="Quiet take" />
      <Audio src={staticFile("vo_reveal.wav")} from={REVEAL_AT} name="VO reveal" />
      <Audio src={staticFile("boosted.wav")} from={BOOSTED_AT} name="Boosted take" />
      <Audio src={staticFile("vo_explain.wav")} from={EXPLAIN_AT} name="VO explain" />
      {/* feature VO + clicks live inside the Features scene */}
      <Audio src={staticFile("vo_cta.wav")} from={CTA_AT} name="VO cta" />

      {/* very subtle ambient bed under everything */}
      <Audio
        src={staticFile("music.wav")}
        volume={(f) =>
          0.11 *
          interpolate(f, [TOTAL_FRAMES - 70, TOTAL_FRAMES - 10], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        }
        name="Music bed"
      />

      <Grain />

      {/* end fade */}
      <AbsoluteFill
        style={{
          background: "black",
          opacity: interpolate(frame, [TOTAL_FRAMES - 18, TOTAL_FRAMES - 2], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.3, 0, 0.7, 1),
          }),
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
