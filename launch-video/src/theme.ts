import { loadFont as loadDisplay } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadBody } from "@remotion/google-fonts/InstrumentSans";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";

const display = loadDisplay();
const body = loadBody();
const mono = loadMono();

export const T = {
  bg: "#0b0f0e",
  panel: "#121816",
  line: "#22302c",
  text: "#e7efec",
  muted: "#8ba39c",
  faint: "#536862",
  accent: "#2fe0b8",
  accentBright: "#55ecc9",
  accentFg: "#04241c",
  danger: "#ff6b6b",
  display: `"${display.fontFamily}", "Avenir Next", sans-serif`,
  ui: `"${body.fontFamily}", "Avenir Next", sans-serif`,
  mono: `"${mono.fontFamily}", "Menlo", monospace`,
};

export const GLYPH_HEIGHTS = [10, 18, 26, 34, 40, 44, 40, 34, 26, 18, 10];
