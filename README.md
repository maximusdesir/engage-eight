# Engage Eight

> A pre-snap prediction and defensive tendency engine for football.

Engage Eight ingests play-by-play data and answers the two questions a defensive
coordinator asks before every snap:

1. **What is the offense most likely to do?** A calibrated run/pass and explosive
   probability (plus a play-leaning), given down, distance, field position, score,
   time, and formation or personnel when available.
2. **What are their tendencies?** A tendency matrix sliced by down and distance,
   field zone, formation, and hash, so you can self-scout or scout an opponent.

It trains on free, open nflverse NFL play-by-play, and also lets you chart a real
opponent by hand so it works for teams that aren't in public datasets.

## Why I built this

I grew up watching Luke Kuechly, Peyton Manning, Tom Brady, and Ray Lewis. What
truly set them apart wasn't athleticism, it was football IQ. Diagnosing what the
offense or defense was going to do before the snap let them play faster and make
plays no one else could.

I play football too, and as a defensive player I've learned how much scout film
matters and how slow it is to watch. I wanted a tool that could speed up film
study and let me quiz myself on my own pre-snap reads.

I believe AI can change football, and I wanted to build something that starts to
show how, even with almost no resources. Now imagine what a team with millions in
budget could do.

## A note on accuracy

Run/pass prediction from the situation lands around 72 to 75 percent. Predicting a
specific play family from public data is much harder (roughly 30 to 45 percent
top-1). The model reports its calibration (Brier score), not just accuracy, and is
validated with time-based splits: train on past seasons, test on the most recent.
A random split would leak the future and inflate the results.

## Project status

| Layer | Status |
|-------|--------|
| Data + ML pipeline (`ml/`) | Working end-to-end on real NFL data |
| API (`api/`) | Working (auth, predict/recommend, tendencies, uploads, vocab) |
| Web app (`web/`) | Working MVP (Vite + React dashboard over the API) |
| Hudl CSV import | Working (breakdown export to plays) |
| Formation/motion vocabulary | Working (canonical vocab + per-team mapping) |

### Measured results (run/pass, 2019-2023)

Trained on 173,881 real run/pass plays from nflverse, with a time-split: train on
2019-2021, calibrate on 2022, test on the fully held-out 2023 season.

| Metric | Value |
|--------|-------|
| Test-season accuracy | 69.7% |
| Naive baseline (always guess majority) | 59.0% |
| ROC-AUC | 0.766 |
| Brier score (lower is better-calibrated) | 0.192 |

The model's top signals are exactly what a coordinator reads: offense identity,
time remaining, field position, score differential, and down and distance. For
example, it calls 89% pass on 3rd-and-8 and 85% run on 3rd-and-1 at the 2-yard
line.

## Roadmap

Done:

- **Formation and pre-snap motion tendencies.** A team lines up in Pro Right on
  3rd down and jet-motions the slot, and the tendency matrix says run. Formation
  and motion are captured from Hudl imports and manual charting, folded onto a
  canonical vocabulary (`ml/engage8/vocab.py`) so a team's naming variants
  ("Trips Rt" / "Trips") combine into one bucket. Unrecognized names are surfaced
  for the coach to map per team; mappings apply on read, no re-import needed. Both
  `formation` and `motion` are tendency splits, and they feed the model as
  categorical features.

- **Web dashboard.** A Vite + React dashboard (`web/`) over the API: sign in,
  upload breakdowns, browse the tendency matrix, map vocabulary, and run
  predict/recommend in the browser.

Planned next, roughly in priority order:

1. **Picture-based vocabulary matching.** Replace the text mapping UI with a
   grid of formation/motion diagrams a coach clicks to map raw names, so no one
   has to know the canonical spelling. The mapping API and the
   `CanonicalPicker` component are already the seam for this.

2. **Per-team and per-coordinator model training.** Instead of one
   league-average model, train or fine-tune a model per opponent so week-to-week
   scouting reflects that specific team's tendencies. This fits the Hudl
   workflow: import a team's breakdown, train on it, and get a scouting-ready
   model for that week.

3. **Hosted deploy.** Ship the dashboard and API to a hosted environment
   (e.g. Vercel + a managed API/Postgres) so coaches use it without a local
   setup.

## Quickstart (ML pipeline)

```bash
cd ml
python -m venv .venv && source .venv/bin/activate   # Python 3.11 or 3.12
pip install -r requirements.txt

# 1. Pull nflverse play-by-play (downloads to ml/data/)
python -m engage8.extract --seasons 2019 2020 2021 2022 2023

# 2. Normalize to the canonical schema and engineer features
python -m engage8.features

# 3. Train the run/pass model (time-split, calibrated)
python -m engage8.train

# 4. Predict a situation
python -m engage8.predict --down 2 --distance 6 --yardline 38 \
    --quarter 2 --clock 252 --score-diff 3
```

## Repo layout

```
engage_eight/
├── ml/        # data pipeline + model training (start here)
├── api/       # FastAPI service (auth, predict, tendencies, uploads, vocab)
└── web/       # Vite + React dashboard
```

## Data sources

- **nflverse / nflfastR** ([github.com/nflverse](https://github.com/nflverse)):
  open NFL play-by-play with EPA and win probability. The pipeline downloads the
  published season parquet files directly, so there's no extra loader dependency.
- **Manual charting**: chart any team's plays into a CSV and run the same tendency
  and prediction engine on them.

## License

MIT, see [LICENSE](LICENSE).
