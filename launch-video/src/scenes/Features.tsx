import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio } from "@remotion/media";
import { T } from "../theme";

const FEATURES = [
  "Every format — MP4 · MOV · MKV · WebM",
  "Batch a whole folder at once",
  "YouTube −14 · Podcast −16 · Broadcast −23",
  "Before / after waveforms",
  "FFmpeg built in — zero setup",
  "Right-click, straight from Finder",
];

/** `rowAts` — scene-relative frames where each row (and its VO) starts. */
export const Features: React.FC<{ rowAts: number[] }> = ({ rowAts }) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill
      style={{
        background: T.bg,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 26,
          letterSpacing: "0.32em",
          color: T.faint,
          textTransform: "uppercase",
          marginBottom: 54,
          opacity: interpolate(frame, [0, 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        In the box
      </div>

      {/* VO + click per row, exactly when it lands */}
      {FEATURES.map((_, i) => (
        <React.Fragment key={`sfx-${i}`}>
          <Audio
            src={staticFile(`vo_f${i + 1}.wav`)}
            from={rowAts[i]}
            name={`Feature VO ${i + 1}`}
          />
          <Audio
            src={staticFile("click.wav")}
            from={rowAts[i]}
            volume={0.5}
            name={`Click ${i + 1}`}
          />
        </React.Fragment>
      ))}

      <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
        {FEATURES.map((f, i) => {
          const a = interpolate(frame, [rowAts[i], rowAts[i] + 16], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          const isCurrent =
            frame >= rowAts[i] &&
            (i === FEATURES.length - 1 || frame < rowAts[i + 1]);
          return (
            <div
              key={f}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 26,
                opacity: a * (isCurrent ? 1 : 0.55),
                translate: `${(1 - a) * 46}px 0px`,
              }}
            >
              <div
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: 99,
                  background: isCurrent ? T.accent : T.faint,
                  boxShadow: isCurrent
                    ? "0 0 16px rgba(47, 224, 184, 0.5)"
                    : "none",
                }}
              />
              <div
                style={{
                  fontFamily: T.ui,
                  fontWeight: 600,
                  fontSize: 52,
                  color: isCurrent ? T.text : T.muted,
                }}
              >
                {f}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
