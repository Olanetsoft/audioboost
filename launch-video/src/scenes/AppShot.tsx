import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { T } from "../theme";

const ROWS = [
  { name: "demo-recording.mp4", size: "414.2 MB", lufs: "−28.4", doneAt: 30 },
  { name: "walkthrough.mov", size: "1.2 GB", lufs: "−31.0", doneAt: 90 },
  { name: "intro.webm", size: "203.5 MB", lufs: "−25.2", doneAt: 150 },
];

export const AppShot: React.FC = () => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 26], [0, 1], {
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
      {/* the app window */}
      <div
        style={{
          width: 760,
          borderRadius: 22,
          background: T.panel,
          border: `2px solid ${T.line}`,
          boxShadow: "0 40px 120px -30px rgba(0,0,0,0.8), 0 0 80px rgba(47,224,184,0.07)",
          padding: "34px 38px 38px",
          opacity: enter,
          scale: String(0.94 + 0.06 * enter),
          translate: `0px ${(1 - enter) * 30}px`,
        }}
      >
        {/* faceplate */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            borderBottom: `1px solid ${T.line}`,
            paddingBottom: 18,
            marginBottom: 22,
          }}
        >
          <div style={{ fontFamily: T.display, fontWeight: 700, fontSize: 30, letterSpacing: "0.13em", color: T.text }}>
            AUDIO<span style={{ color: T.accent }}>BOOST</span>
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 13, letterSpacing: "0.2em", color: T.faint }}>
            <span
              style={{
                display: "inline-block",
                width: 9,
                height: 9,
                borderRadius: 99,
                background: T.accent,
                marginRight: 9,
                boxShadow: "0 0 8px rgba(47,224,184,0.6)",
                opacity: 0.5 + 0.5 * Math.sin(frame / 5) ** 2,
              }}
            />
            RUN
          </div>
        </div>

        {/* segmented control */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            background: T.bg,
            border: `1.5px solid ${T.line}`,
            borderRadius: 13,
            padding: 4,
            marginBottom: 20,
            fontFamily: T.ui,
            fontWeight: 600,
            fontSize: 18,
            textAlign: "center",
          }}
        >
          <div style={{ background: T.accent, color: T.accentFg, borderRadius: 9, padding: "10px 0", boxShadow: "0 2px 14px rgba(47,224,184,0.35)" }}>
            YouTube −14
          </div>
          <div style={{ color: T.muted, padding: "10px 0" }}>Podcast −16</div>
          <div style={{ color: T.muted, padding: "10px 0" }}>Broadcast −23</div>
        </div>

        {/* queue rows: tick to done one after another */}
        <div style={{ border: `1.5px solid ${T.line}`, borderRadius: 14, overflow: "hidden", marginBottom: 22 }}>
          {ROWS.map((r, i) => {
            const done = frame >= r.doneAt;
            const active = !done && (i === 0 || frame >= ROWS[i - 1].doneAt);
            return (
              <div
                key={r.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "13px 18px",
                  borderBottom: i < ROWS.length - 1 ? `1px solid ${T.line}` : "none",
                  fontFamily: T.ui,
                  fontSize: 18,
                  color: done ? T.text : active ? T.accent : T.muted,
                }}
              >
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 99,
                    background: done ? "#43d17c" : active ? T.accent : T.faint,
                    boxShadow: active ? "0 0 8px rgba(47,224,184,0.6)" : "none",
                    opacity: active ? 0.5 + 0.5 * Math.sin(frame / 3) ** 2 : 1,
                  }}
                />
                <span style={{ flex: 1, fontWeight: 500 }}>{r.name}</span>
                <span
                  style={{
                    fontFamily: T.mono,
                    fontSize: 13,
                    color: T.accent,
                    background: "rgba(47,224,184,0.12)",
                    borderRadius: 6,
                    padding: "3px 8px",
                  }}
                >
                  {r.lufs} LUFS
                </span>
                <span style={{ fontFamily: T.mono, fontSize: 13, color: T.muted }}>{r.size}</span>
              </div>
            );
          })}
        </div>

        {/* mini waveform strip */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            height: 62,
            border: `1.5px solid ${T.line}`,
            borderRadius: 14,
            marginBottom: 24,
          }}
        >
          {Array.from({ length: 40 }, (_, i) => {
            const env = Math.sin((i / 40) * Math.PI * 4.5) ** 2;
            const grow = interpolate(frame, [20 + i * 2, 44 + i * 2], [0.15, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            });
            return (
              <div
                key={i}
                style={{
                  width: 8,
                  height: Math.max(4, env * 44 * grow),
                  borderRadius: 99,
                  background: grow > 0.6 ? T.accent : T.faint,
                }}
              />
            );
          })}
        </div>

        {/* primary button */}
        <div
          style={{
            display: "inline-block",
            fontFamily: T.ui,
            fontWeight: 600,
            fontSize: 20,
            background: T.accent,
            color: T.accentFg,
            borderRadius: 12,
            padding: "13px 30px",
            boxShadow: "0 4px 22px rgba(47,224,184,0.35)",
          }}
        >
          Boost Audio
        </div>
      </div>

      <div
        style={{
          fontFamily: T.ui,
          fontWeight: 600,
          fontSize: 40,
          color: T.muted,
          opacity: interpolate(frame, [30, 50], [0, 1], {
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
