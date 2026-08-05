import React from "react";
import { Easing, interpolate, random, useCurrentFrame } from "remotion";
import { T } from "../theme";

const BAR_COUNT = 56;

/**
 * A speech-like waveform strip. `boost` (0..1) morphs it from a barely
 * visible gray trace into full teal bars — the product moment.
 */
export const WaveRow: React.FC<{
  boost: number;
  width?: number;
  height?: number;
}> = ({ boost, width = 1280, height = 220 }) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        alignItems: "center",
        gap: (width / BAR_COUNT) * 0.35,
        justifyContent: "center",
      }}
    >
      {Array.from({ length: BAR_COUNT }, (_, i) => {
        // stable speech-ish envelope: syllable clusters with gaps
        const seed = random(`bar-${i}`);
        const cluster = Math.sin((i / BAR_COUNT) * Math.PI * 5.2) ** 2;
        const envelope = 0.18 + 0.82 * cluster * (0.45 + 0.55 * seed);
        // tiny live shimmer so the strip never looks frozen
        const shimmer = 1 + 0.06 * Math.sin(frame / 3 + i * 1.7);

        const quiet = envelope * 0.09;
        const loud = envelope * shimmer;
        const level = quiet + (loud - quiet) * boost;

        // bars near the sweep edge light up first; fully dark at zero boost
        const sweep =
          boost <= 0
            ? 0
            : interpolate(boost, [i / BAR_COUNT - 0.12, i / BAR_COUNT + 0.05], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              });

        return (
          <div
            key={i}
            style={{
              flex: 1,
              height: Math.max(4, level * height),
              borderRadius: 99,
              background: sweep > 0.5 ? T.accent : T.faint,
              opacity: 0.35 + 0.65 * Math.max(sweep, 0.3),
              boxShadow:
                sweep > 0.5 ? "0 0 18px rgba(47, 224, 184, 0.35)" : "none",
            }}
          />
        );
      })}
    </div>
  );
};
