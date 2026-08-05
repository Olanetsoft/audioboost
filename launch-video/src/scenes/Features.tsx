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
  "MP4 · MOV · MKV · WebM in — MP4 out",
  "Batch queue with per-file loudness readout",
  "YouTube −14 · Podcast −16 · Broadcast −23",
  "Before / after waveform preview",
  "FFmpeg bundled — zero setup",
  "Right-click any video in Finder",
];

export const Features: React.FC = () => {
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
      {/* one UI click as each row lands */}
      {FEATURES.map((f, i) => (
        <Audio
          key={`click-${f}`}
          src={staticFile("click.wav")}
          from={6 + i * 9}
          volume={0.55}
          name={`Click ${i + 1}`}
        />
      ))}
      <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
        {FEATURES.map((f, i) => (
          <div
            key={f}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 26,
              opacity: interpolate(frame, [6 + i * 9, 22 + i * 9], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              }),
              translate: `${
                (1 -
                  interpolate(frame, [6 + i * 9, 22 + i * 9], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: Easing.bezier(0.16, 1, 0.3, 1),
                  })) *
                46
              }px 0px`,
            }}
          >
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: 99,
                background: T.accent,
                boxShadow: "0 0 16px rgba(47, 224, 184, 0.5)",
              }}
            />
            <div
              style={{
                fontFamily: T.ui,
                fontWeight: 600,
                fontSize: 52,
                color: T.text,
              }}
            >
              {f}
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
