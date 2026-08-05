import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { WaveRow } from "../components/WaveRow";
import { T } from "../theme";

export const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const appear = (from: number, to: number) =>
    interpolate(frame, [from, to], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });

  return (
    <AbsoluteFill
      style={{
        background: T.bg,
        justifyContent: "center",
        alignItems: "center",
        gap: 64,
      }}
    >
      <div
        style={{
          fontFamily: T.ui,
          fontWeight: 600,
          fontSize: 66,
          color: T.text,
          opacity: appear(4, 22),
          translate: `0px ${(1 - appear(4, 22)) * 24}px`,
        }}
      >
        Ever recorded with the mic too low?
      </div>

      <div style={{ opacity: appear(14, 30) }}>
        <WaveRow boost={0} />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 26,
          fontFamily: T.mono,
          opacity: appear(20, 36),
        }}
      >
        <span style={{ fontSize: 30, color: T.faint, letterSpacing: "0.2em" }}>
          MEASURED
        </span>
        <span style={{ fontSize: 76, color: T.danger, fontWeight: 700 }}>
          −45.5 LUFS
        </span>
        <span style={{ fontSize: 30, color: T.faint }}>· barely audible</span>
      </div>
    </AbsoluteFill>
  );
};
