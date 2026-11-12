// Types and display helpers for the public "Call it" quiz. The plays are a
// static file exported by ml/engage8/quiz.py, so this page never calls the API.

export type Call = "run" | "pass";

export type QuizPlay = {
  id: string;
  week: number;
  offense: string;
  defense: string;
  down: number;
  distance: number;
  yardline_100: number;
  quarter: number;
  clock: number; // game seconds remaining
  score_diff: number; // offense's lead (negative = trailing)
  timeouts: number;
  shotgun: number;
  no_huddle: number;
  actual: Call;
  desc: string;
  model_pass_prob: number;
};

export type QuizFile = { season: number; plays: QuizPlay[] };

const ORDINAL = ["", "1st", "2nd", "3rd", "4th"];

export const downAndDistance = (p: QuizPlay) =>
  `${ORDINAL[p.down] ?? `${p.down}th`} & ${p.distance}`;

/** yardline_100 counts yards to the opponent's goal line. */
export function fieldPosition(p: QuizPlay): string {
  if (p.yardline_100 === 50) return "midfield";
  return p.yardline_100 > 50
    ? `own ${100 - p.yardline_100}`
    : `opp ${p.yardline_100}`;
}

/** Time left in the quarter (game clock is seconds left in the game). */
export function quarterClock(p: QuizPlay): string {
  const left = p.quarter >= 5 ? p.clock : p.clock - (4 - p.quarter) * 900;
  const s = Math.min(Math.max(Math.round(left), 0), 900);
  const label = p.quarter >= 5 ? "OT" : `Q${p.quarter}`;
  return `${label} ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export const alignment = (p: QuizPlay) =>
  `${p.shotgun ? "Shotgun" : "Under center"}${p.no_huddle === 1 ? ", no huddle" : ""}`;

export function scoreText(p: QuizPlay): string {
  if (p.score_diff === 0) return "Tied";
  return p.score_diff > 0
    ? `Leading by ${p.score_diff}`
    : `Trailing by ${-p.score_diff}`;
}

export const modelCall = (p: QuizPlay): Call =>
  p.model_pass_prob >= 0.5 ? "pass" : "run";

/** Fisher-Yates shuffle into a new array. */
export function shuffled<T>(items: T[]): T[] {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
