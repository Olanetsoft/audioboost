import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { T } from "../theme";

/** Letter-staggered AUDIOBOOST wordmark with a springy rise. */
export const Wordmark: React.FC<{ size?: number; from?: number }> = ({
  size = 92,
  from = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const letters = "AUDIOBOOST".split("");

  return (
    <div
      style={{
        display: "flex",
        fontFamily: T.display,
        fontWeight: 800,
        fontSize: size,
        letterSpacing: "0.1em",
      }}
    >
      {letters.map((ch, i) => {
        const s = spring({
          frame: frame - from - i * 2,
          fps,
          config: { damping: 14, stiffness: 160, mass: 0.6 },
        });
        return (
          <span
            key={i}
            style={{
              color: i < 5 ? T.text : T.accent,
              opacity: s,
              translate: `0px ${(1 - s) * 42}px`,
              scale: String(0.7 + 0.3 * s),
              textShadow:
                i >= 5 ? "0 0 34px rgba(47, 224, 184, 0.35)" : "none",
            }}
          >
            {ch}
          </span>
        );
      })}
    </div>
  );
};
