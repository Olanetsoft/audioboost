import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { WaveRow } from "../components/WaveRow";
import { T } from "../theme";

export const Boost: React.FC = () => {
  const frame = useCurrentFrame();

  // the drop: file chip falls in, then the sweep boosts the waveform
  const drop = interpolate(frame, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.4, 0.44, 1),
  });
  const boost = interpolate(frame, [26, 78], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const lufs = interpolate(frame, [26, 84], [-41.5, -14.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const settleGlow = interpolate(frame, [84, 100], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

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
        <span
          style={{
            fontSize: 30,
            color: T.accent,
            opacity: settleGlow,
          }}
        >
          · no clipping
        </span>
      </div>

      <div
        style={{
          fontFamily: T.ui,
          fontWeight: 600,
          fontSize: 46,
          color: T.text,
          opacity: interpolate(frame, [96, 116], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        Two-pass EBU R128 · video stream untouched
      </div>
    </AbsoluteFill>
  );
};
