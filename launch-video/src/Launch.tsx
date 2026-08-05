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
import { Hook } from "./scenes/Hook";
import { Problem } from "./scenes/Problem";
import { Boost } from "./scenes/Boost";
import { Features } from "./scenes/Features";
import { Outro } from "./scenes/Outro";
import { T } from "./theme";

// Timeline at 30 fps. Total: 750 frames = 25 s.
const HOOK_START = 0;
const PROBLEM_START = 75; // 2.5 s
const BOOST_START = 225; // 7.5 s
const FEATURES_START = 465; // 15.5 s
const OUTRO_START = 615; // 20.5 s
export const TOTAL_FRAMES = 750;

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
      {/* scenes */}
      <Sequence from={HOOK_START} durationInFrames={PROBLEM_START - HOOK_START} name="Hook">
        <Hook />
      </Sequence>
      <Sequence from={PROBLEM_START} durationInFrames={BOOST_START - PROBLEM_START} name="Problem">
        <Problem />
      </Sequence>
      <Sequence from={BOOST_START} durationInFrames={FEATURES_START - BOOST_START} name="Boost">
        <Boost />
      </Sequence>
      <Sequence from={FEATURES_START} durationInFrames={OUTRO_START - FEATURES_START} name="Features">
        <Features />
      </Sequence>
      <Sequence from={OUTRO_START} durationInFrames={TOTAL_FRAMES - OUTRO_START} name="Outro">
        <Outro />
      </Sequence>

      {/* audio — the quiet take and its AudioBoost-processed versions */}
      <Audio src={staticFile("quiet.wav")} from={PROBLEM_START + 24} name="Quiet take" />
      <Audio src={staticFile("boosted.wav")} from={BOOST_START + 26} name="Boosted take" />
      <Audio src={staticFile("vo_boost.wav")} from={BOOST_START + 130} name="Boost VO" />
      <Audio src={staticFile("vo_outro.wav")} from={OUTRO_START + 14} name="Outro VO" />

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
