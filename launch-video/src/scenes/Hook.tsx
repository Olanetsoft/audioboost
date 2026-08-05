import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Glyph } from "../components/Glyph";
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
          fontSize: 30,
          letterSpacing: "0.42em",
          color: T.accent,
          textTransform: "uppercase",
          opacity: interpolate(frame, [2, 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        Announcing
      </div>
      <Glyph scale={1.4} appearFrom={6} />
      <div
        style={{
          fontFamily: T.display,
          fontWeight: 700,
          fontSize: 92,
          letterSpacing: "0.14em",
          color: T.text,
          opacity: interpolate(frame, [16, 34], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          translate: interpolate(frame, [16, 34], ["0px 26px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        AUDIO<span style={{ color: T.accent }}>BOOST</span>
      </div>
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 26,
          letterSpacing: "0.32em",
          color: T.faint,
          textTransform: "uppercase",
          opacity: interpolate(frame, [30, 48], [0, 1], {
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
