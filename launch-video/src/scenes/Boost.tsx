import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { WaveRow } from "../components/WaveRow";
import { T } from "../theme";

/** `sweepFrom` — frame (scene-relative) where the boosted take starts. */
export const Boost: React.FC<{ sweepFrom: number }> = ({ sweepFrom }) => {
  const frame = useCurrentFrame();

  const drop = interpolate(frame, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.4, 0.44, 1),
  });
  const boost = interpolate(frame, [sweepFrom, sweepFrom + 52], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const lufs = interpolate(frame, [sweepFrom, sweepFrom + 58], [-45.5, -14.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const settleGlow = interpolate(
    frame,
    [sweepFrom + 58, sweepFrom + 74],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        background: T.bg,
        justifyContent: "center",
        alignItems: "center",
        gap: 56,
      }}
    >
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 30,
          letterSpacing: "0.12em",
          color: T.muted,
          background: T.panel,
          border: `2px solid ${T.line}`,
          borderRadius: 16,
          padding: "18px 34px",
          translate: `0px ${(1 - drop) * -160}px`,
          opacity: drop,
        }}
      >
        recording.mp4 → <span style={{ color: T.accent }}>AudioBoost</span>
      </div>

      <WaveRow boost={boost} />

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 26,
          fontFamily: T.mono,
        }}
      >
        <span style={{ fontSize: 30, color: T.faint, letterSpacing: "0.2em" }}>
          NORMALIZED
        </span>
        <span
          style={{
            fontSize: 84,
            fontWeight: 700,
            color: boost > 0.55 ? T.accent : T.muted,
            textShadow:
              settleGlow > 0
                ? `0 0 ${34 * settleGlow}px rgba(47, 224, 184, 0.55)`
                : "none",
          }}
        >
          {lufs.toFixed(1)} LUFS
        </span>
        <span style={{ fontSize: 30, color: T.accent, opacity: settleGlow }}>
          · no clipping
        </span>
      </div>
    </AbsoluteFill>
  );
};
