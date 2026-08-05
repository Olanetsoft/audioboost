import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Glyph } from "../components/Glyph";
import { Wordmark } from "../components/Wordmark";
import { T } from "../theme";

export const Hook: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill
      style={{
        background: T.bg,
        justifyContent: "center",
        alignItems: "center",
        gap: 48,
      }}
    >
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 28,
          letterSpacing: `${interpolate(frame, [2, 26], [0.9, 0.44], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}em`,
          color: T.accent,
          textTransform: "uppercase",
          opacity: interpolate(frame, [2, 16], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        Announcing
      </div>
      <Glyph scale={1.4} appearFrom={8} />
      <Wordmark from={14} />
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 25,
          letterSpacing: "0.3em",
          color: T.faint,
          textTransform: "uppercase",
          opacity: interpolate(frame, [40, 58], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        Loudness Normalizer for macOS
      </div>
    </AbsoluteFill>
  );
};
