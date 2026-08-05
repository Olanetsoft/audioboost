import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { GLYPH_HEIGHTS, T } from "../theme";

export const Glyph: React.FC<{
  scale?: number;
  color?: string;
  appearFrom?: number;
  dance?: boolean;
}> = ({ scale = 1, color = T.accent, appearFrom = 0, dance = false }) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10 * scale,
        height: 88 * scale,
      }}
    >
      {GLYPH_HEIGHTS.map((h, i) => {
        const pop = interpolate(
          frame,
          [appearFrom + i * 2, appearFrom + i * 2 + 14],
          [0, 1],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          },
        );
        // gentle idle sway; energetic when dancing
        const phase = Math.sin((frame / (dance ? 4 : 16)) + i * 1.1);
        const sway = dance ? 0.55 + 0.6 * Math.abs(phase) : 0.92 + 0.08 * phase;
        return (
          <div
            key={i}
            style={{
              width: 13 * scale,
              height: h * 2 * scale,
              borderRadius: 7 * scale,
              background: color,
              scale: String(pop),
              transformOrigin: "center",
              // eslint-disable-next-line @remotion/no-string-transforms
              transform: `scaleY(${sway * pop})`,
              boxShadow: `0 0 ${22 * scale}px rgba(47, 224, 184, 0.35)`,
            }}
          />
        );
      })}
    </div>
  );
};
