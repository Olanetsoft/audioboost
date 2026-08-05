import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Glyph } from "../components/Glyph";
import { Wordmark } from "../components/Wordmark";
import { T } from "../theme";

export const Outro: React.FC = () => {
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
        gap: 44,
      }}
    >
      <Glyph scale={1.1} appearFrom={0} />
      <Wordmark size={84} from={6} />
      <div
        style={{
          fontFamily: T.ui,
          fontWeight: 600,
          fontSize: 44,
          color: T.muted,
          opacity: appear(18, 34),
        }}
      >
        Free · Open source · MIT
      </div>
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 40,
          color: T.accent,
          background: T.panel,
          border: `2px solid ${T.line}`,
          borderRadius: 16,
          padding: "20px 44px",
          opacity: appear(26, 42),
          translate: `0px ${(1 - appear(26, 42)) * 22}px`,
        }}
      >
        github.com/Olanetsoft/audioboost
      </div>
    </AbsoluteFill>
  );
};
