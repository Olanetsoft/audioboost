import t from "./timings.json";

// Every offset derives from the measured VO durations in timings.json —
// regenerate the audio, re-run scripts/measure (or the pipeline), and the
// video re-times itself with no dead air.
export const FPS = 30;
const fr = (s: number) => Math.round(s * FPS);
const GAP = 8; // breath between VO beats

export const PROBLEM_START = 0;
export const PROBLEM_AT = PROBLEM_START + 10;
export const QUIET_AT = PROBLEM_AT + fr(t.vo_problem) + GAP;

export const BOOST_START = QUIET_AT + fr(t.quiet) + 14;
export const REVEAL_AT = BOOST_START + 4;
export const BOOSTED_AT = REVEAL_AT + fr(t.vo_reveal) + GAP;

export const APP_START = BOOSTED_AT + fr(t.boosted) + 14;
export const EXPLAIN_AT = APP_START + 8;

export const FEATURES_START = EXPLAIN_AT + fr(t.vo_explain) + GAP;
const FEATURE_DURS = [t.vo_f1, t.vo_f2, t.vo_f3, t.vo_f4, t.vo_f5, t.vo_f6];
export const FEATURE_ATS: number[] = [];
{
  let cursor = FEATURES_START + 8;
  for (const d of FEATURE_DURS) {
    FEATURE_ATS.push(cursor);
    cursor += fr(d) + 6;
  }
}
const FEATURES_END =
  FEATURE_ATS[FEATURE_ATS.length - 1] + fr(FEATURE_DURS[FEATURE_DURS.length - 1]);

export const OUTRO_START = FEATURES_END + 14;
export const CTA_AT = OUTRO_START + 10;
export const TOTAL_FRAMES = CTA_AT + fr(t.vo_cta) + 40;
