# Engage Eight ML pipeline

The data and model layer. It pulls open nflverse play-by-play, engineers pre-snap
features, and trains a calibrated run/pass model. It also includes a tendency
engine and CSV loaders (Hudl exports, manual charting) for your own opponents.

The trained model is committed in `models/` (`runpass.txt` is the LightGBM
model, `runpass.json` holds the feature list, calibration, and test metrics), so
you only need the pipeline to retrain.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.11 to 3.14
pip install -r requirements.txt
```

## Pipeline

```bash
# 1. Pull and normalize nflverse pbp into data/processed/plays.parquet
python -m engage8.extract --seasons 2019 2020 2021 2022 2023

# 2. Engineer features into data/processed/features.parquet
python -m engage8.features

# 3. Train the run/pass model (time-split + calibration) into models/
python -m engage8.train

# 4. Predict a situation (--shotgun / --under-center / --no-huddle optional)
python -m engage8.predict --down 3 --distance 8 --yardline 45 --quarter 4 --clock 600 --shotgun

# 5. Inspect tendencies
python -m engage8.tendencies --team KC --split down_distance
```

## Bring your own opponent (manual charting)

For a team that isn't in nflverse (your actual opponent):

```bash
python -m engage8.charting --template          # writes data/charting_template.csv
# chart the film, one row per play
python -m engage8.charting --load my_opponent.csv   # tendencies on charted data
```

Already have Hudl? Export a breakdown as CSV and load it directly. The adapter
maps Hudl's columns (DN, DIST, YARD LN, ODK, QTR, OFF FORM, OFF PLAY, PLAY TYPE,
BACKFIELD, TEMPO, ...) into the canonical schema, converts the yard line (negative
= own side, positive = opponent side), and keeps offensive run/pass plays. Blank
cells are fine.

Run vs pass comes from the PLAY TYPE column, or else from the play name ("Mesh"
is a pass, "Inside Zone" a run, "PA Power" a pass). Names it can't call, like
"RPO Glance" or a team code like "Black 23", are skipped and listed so you can
add a PLAY TYPE column rather than losing them silently. Shotgun is read from a
BACKFIELD/SHOTGUN column or from "Gun"/"Pistol"/"UC" in the formation name.

```bash
python -m engage8.hudl --template              # writes a sample Hudl-style CSV
python -m engage8.hudl --load hudl_export.csv --team LINCOLN
```

## Module map

| Module | Job |
|--------|-----|
| `config.py` | Paths and the canonical `Play` schema every source maps into |
| `extract.py` | nflverse pull into the canonical schema |
| `features.py` | Pre-snap situational features + shotgun/no-huddle |
| `train.py` | LightGBM run/pass, time-split, isotonic calibration, metrics |
| `predict.py` | Calibrated prediction with a "why" (single or batch) |
| `tendencies.py` | Run/pass and top-play aggregation by down/dist, zone, formation, motion, quarter, hash |
| `charting.py` | Manual opponent charting CSV into the canonical schema |
| `hudl.py` | Hudl breakdown CSV adapter (maps Hudl columns into the schema) |
| `parsing.py` | Null-safe parsing shared by the CSV loaders (run/pass, shotgun, tempo) |
| `vocab.py` | Canonical formation/motion vocabulary and normalization |

## Why these choices

- **LightGBM**: best on tabular pre-snap data, handles missing values natively
  (nflverse is full of nulls), trains in seconds, and is explainable.
- **Time-based split**: train on older seasons, test on the newest. A random split
  leaks the future and inflates accuracy, which is the most common football-ML
  mistake.
- **Calibration**: a coach only trusts "63% pass" if it is right about 63 percent
  of the time, so the model reports its Brier score, not just accuracy.
- **Label = called dropback** (`qb_dropback`): scrambles and sacks are passes the
  defense had to defend. nflverse's `play_type` files scrambles under "run",
  which put about 7% designed passes in the run class.
- **Only coach-knowable inputs**: down, distance, field position, clock, score,
  timeouts, shotgun, no-huddle. NFL team identity was dropped (it can't transfer
  to your opponent, and removing it slightly improved test accuracy). Formation,
  personnel, motion, and hash are null in public NFL data, so they are not model
  features; they feed the API's per-opponent blend instead. Shotgun/no-huddle are
  blanked on 25% of training rows so "unknown" is a real input, not "under
  center".
- **No previous-play features**: with the previous plays known they added 0.3
  points of accuracy; blank (the usual case at serve time) they scored worse
  than leaving them out.

## Tests

```bash
python -m pytest   # synthetic data + CSV fixtures in tests/fixtures, no network
```

`tests/fixtures/` holds Hudl-shaped exports (BOM header, blank QTR cells, kick
rows, a file without a PLAY TYPE column). Add real exports there as you get them.

## Accuracy

On the held-out 2023 season: 74.1% with shotgun/no-huddle known, 70.5% from the
situation alone, vs 61.3% for always guessing pass (AUC 0.816 / 0.785, Brier
0.169 / 0.181). Predicting a specific play family is much harder and not
attempted.
