import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { WaveRow } from "../components/WaveRow";
import { T } from "../theme";

/** `listenFrom` — frame (scene-relative) where the quiet take starts playing. */
export const Problem: React.FC<{ listenFrom: number }> = ({ listenFrom }) => {
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
        You finish a recording… and the mic was too low.
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
          opacity: appear(listenFrom - 6, listenFrom + 8),
        }}
      >
        <span
          style={{
            fontSize: 30,
            color: T.accent,
            letterSpacing: "0.2em",
            opacity: 0.5 + 0.5 * Math.sin(frame / 4) ** 2,
          }}
        >
          ▶ LISTEN
        </span>
        <span style={{ fontSize: 76, color: T.danger, fontWeight: 700 }}>
          −46.7 LUFS
        </span>
        <span style={{ fontSize: 30, color: T.faint }}>· barely audible</span>
      </div>
    </AbsoluteFill>
  );
};
