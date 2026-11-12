"""Generate the fictional "Central HS" demo opponent as a Hudl-style CSV.

Central HS is made up. Nothing here comes from a real team or real film: the
plays are drawn from a seeded random model with tendencies written in on
purpose, so the demo has something clear to find:

  * from I-Form they run about 70% of the time
  * from Empty they pass about 90% of the time
  * with jet motion they run about 90% of the time
  * on 3rd and long they mostly pass, and in short yardage they run

The output goes through the same Hudl loader a real export does (BOM header,
kicking rows, direction words in formation names), so it also exercises ingest.

    python ml/scripts/make_sample_opponent.py            # writes api/demo/central_hs.csv
    python ml/scripts/make_sample_opponent.py --seed 3 --out /tmp/other.csv

The same seed always writes the same file; a test checks the committed CSV
against this script.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

TEAM = "Central HS (fictional)"
OPPONENTS = ["Northside", "Lakeview", "Westfield", "Riverton", "St. Mary's"]
GAMES = 5
PLAYS_PER_GAME = 50          # offensive plays, so 250 in all
SEED = 67

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "api" / "demo" / "central_hs.csv"

COLUMNS = [
    "PLAY #", "ODK", "QTR", "DN", "DIST", "HASH", "YARD LN", "OFF FORM",
    "OFF PLAY", "PLAY TYPE", "RESULT", "GN/LS", "MOTION", "BACKFIELD",
    "OFF TEAM", "DEF TEAM",
]

# Raw formation names as a coach would type them, with the base weight each
# gets and the log-odds of a pass from it. Direction words are on purpose:
# the vocab step folds "Trips Rt" and "Trips Lt" onto TRIPS.
FORMATIONS = {
    #  name          weight  pass log-odds  QB alignment
    "I-Form":      (0.28,  -1.00, "UC"),
    "Heavy":       (0.06,  -1.80, "UC"),
    "Pro Lt":      (0.10,  -0.60, "UC"),
    "Pro Rt":      (0.09,  -0.60, "UC"),
    "Doubles":     (0.18,  -0.30, "Gun"),
    "Trips Rt":    (0.12,   0.10, "Gun"),
    "Trips Lt":    (0.12,   0.10, "Gun"),
    "Empty":       (0.09,   1.50, "Gun"),
}
JET_LOGODDS = -3.0
MOTIONS_BY_FORMATION = {   # formations that ever use motion -> (jet, orbit, across)
    "Pro Lt": (0.15, 0.04, 0.04), "Pro Rt": (0.15, 0.04, 0.04),
    "Doubles": (0.24, 0.06, 0.05),
    "Trips Rt": (0.24, 0.06, 0.05), "Trips Lt": (0.24, 0.06, 0.05),
}
RUN_PLAYS_I = ["Iso", "Power", "Inside Zone", "Counter", "Toss"]
RUN_PLAYS = ["Inside Zone", "Outside Zone", "Duo", "Draw", "Counter"]
PASS_PLAYS = ["Stick", "Smash", "Curl Flat", "Slant", "PA Boot", "Screen"]
PASS_PLAYS_EMPTY = ["Mesh", "Four Verts", "Smash", "Slant"]


def _weighted(rng, names, weights):
    w = np.array(weights, dtype=float)
    return names[int(rng.choice(len(names), p=w / w.sum()))]


def _formation(rng, down: int, dist: int, yl: int) -> str:
    names = list(FORMATIONS)
    w = {n: FORMATIONS[n][0] for n in names}
    if dist <= 2 or yl <= 3:                 # short yardage: big sets
        w["I-Form"] *= 3.0; w["Heavy"] *= 4.0; w["Empty"] *= 0.1
    elif dist >= 7:                          # long: spread out
        for n in ("Trips Rt", "Trips Lt"):
            w[n] *= 1.6
        w["Doubles"] *= 1.4; w["Empty"] *= 2.5; w["I-Form"] *= 0.3; w["Heavy"] *= 0.1
    return _weighted(rng, names, [w[n] for n in names])


def _motion(rng, formation: str) -> str:
    probs = MOTIONS_BY_FORMATION.get(formation)
    if not probs:
        return ""
    r = rng.random()
    if r < probs[0]:
        return "Jet Rt" if rng.random() < 0.5 else "Jet Lt"
    if r < probs[0] + probs[1]:
        return "Orbit"
    if r < sum(probs):
        return "Across"
    return ""


def _is_pass(rng, formation: str, motion: str, down: int, dist: int, yl: int) -> bool:
    z = FORMATIONS[formation][1]
    if dist >= 7:
        z += 0.9 + (1.0 if down >= 3 else 0.0)   # third and long is a pass
    elif dist <= 2:
        z -= 1.3
    if down == 3 and 4 <= dist < 7:
        z += 0.6
    if down == 1:
        z -= 0.2
    if yl <= 10:
        z -= 0.2
    if motion.startswith("Jet"):
        z += JET_LOGODDS
    elif motion:
        z += 0.3
    return bool(rng.random() < 1 / (1 + np.exp(-z)))


def _run_result(rng, formation: str, motion: str) -> tuple[str, str, int]:
    if motion.startswith("Jet"):
        play = "Jet Sweep" if rng.random() < 0.75 else "Reverse"
        yards = int(round(rng.gamma(2.0, 2.6) - 0.6))
    else:
        play = rng.choice(RUN_PLAYS_I if formation in ("I-Form", "Heavy") else RUN_PLAYS)
        yards = int(round(rng.gamma(2.4, 2.1) - 0.6))
    return str(play), "Rush", int(np.clip(yards, -6, 40))


def _pass_result(rng, formation: str, dist: int) -> tuple[str, str, int]:
    play = rng.choice(PASS_PLAYS_EMPTY if formation == "Empty" else PASS_PLAYS)
    r = rng.random()
    sack_p = 0.09 if dist >= 7 else 0.04
    if r < sack_p:
        return str(play), "Sack", -int(rng.integers(4, 10))
    if r < sack_p + 0.30:
        return str(play), "Incomplete", 0
    yards = int(round(rng.gamma(2.0, 4.5) + 1))
    return str(play), "Complete", int(np.clip(yards, 1, 60))


def generate(seed: int = SEED) -> list[dict]:
    """Return CSV rows (dicts keyed by COLUMNS) for all games."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        row = {c: "" for c in COLUMNS}
        row.update({"PLAY #": n, "OFF TEAM": TEAM}, **kw)
        rows.append(row)

    def yard_ln(yl: int):
        """yardline_100 -> Hudl signed: negative is own side."""
        return 50 if yl == 50 else (-(100 - yl) if yl > 50 else yl)

    for g in range(GAMES):
        opp = OPPONENTS[g % len(OPPONENTS)]
        game_rows_start, off_plays = len(rows), 0
        add(ODK="K", QTR=1, **{"YARD LN": -35, "PLAY TYPE": "KO", "RESULT": "Touchback", "DEF TEAM": opp})
        yl, down, dist = int(rng.integers(62, 82)), 1, 10

        while off_plays < PLAYS_PER_GAME:
            qtr = 1 + off_plays * 4 // PLAYS_PER_GAME
            hash_ = str(rng.choice(["L", "M", "R"], p=[0.3, 0.4, 0.3]))
            if down == 4:
                if yl <= 33:
                    add(ODK="K", QTR=qtr, **{"YARD LN": yard_ln(yl), "PLAY TYPE": "FG",
                                             "RESULT": "Good" if rng.random() < 0.7 else "No Good",
                                             "DEF TEAM": opp})
                    yl, down, dist = int(rng.integers(66, 80)), 1, 10
                    continue
                if not (yl <= 45 and rng.random() < 0.2):
                    add(ODK="K", QTR=qtr, **{"YARD LN": yard_ln(yl), "PLAY TYPE": "Punt",
                                             "RESULT": "Fair Catch", "DEF TEAM": opp})
                    yl, down, dist = int(rng.integers(58, 80)), 1, 10
                    continue

            form = _formation(rng, down, dist, yl)
            motion = _motion(rng, form)
            if _is_pass(rng, form, motion, down, dist, yl):
                play, result, gain = _pass_result(rng, form, dist)
                ptype = "Pass"
            else:
                play, result, gain = _run_result(rng, form, motion)
                ptype = "Run"
            gain = min(gain, yl)
            add(ODK="O", QTR=qtr, DN=down, DIST=dist, HASH=hash_, **{
                "YARD LN": yard_ln(yl), "OFF FORM": form, "OFF PLAY": play,
                "PLAY TYPE": ptype, "RESULT": result, "GN/LS": gain, "MOTION": motion,
                "BACKFIELD": FORMATIONS[form][2], "DEF TEAM": opp})
            off_plays += 1

            yl -= gain
            if yl <= 0:                                   # touchdown, kick off
                rows[-1]["RESULT"] = f"{result} TD"
                add(ODK="K", QTR=qtr, **{"YARD LN": -35, "PLAY TYPE": "KO",
                                         "RESULT": "Touchback", "DEF TEAM": opp})
                yl, down, dist = int(rng.integers(62, 82)), 1, 10
            elif gain >= dist:
                down, dist = 1, min(10, yl)
            else:
                down, dist = down + 1, dist - gain
                if down == 5:                             # turnover on downs
                    yl, down, dist = int(rng.integers(55, 80)), 1, 10
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: a BOM on the header row, like a real Hudl export.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Write the fictional Central HS demo CSV.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    rows = generate(args.seed)
    write_csv(rows, args.out)
    off = sum(r["ODK"] == "O" for r in rows)
    print(f"Wrote {len(rows)} rows ({off} offensive plays) -> {args.out}")


if __name__ == "__main__":
    main()
