# Engage Eight

> A pre-snap prediction and defensive tendency engine for football.

Engage Eight ingests play-by-play data and answers the two questions a defensive
coordinator asks before every snap:

1. **What is the offense most likely to do?** A calibrated run/pass probability
   given down, distance, field position, score, time, and whether the QB is in
   shotgun and the offense is in no-huddle. When you've uploaded film on the
   opponent, their own tendencies (overall, in that down and distance, out of
   that formation and motion) are blended in on top of the league model.
2. **What are their tendencies?** A tendency matrix sliced by down and distance,
   field zone, formation, pre-snap motion, quarter, and hash, so you can
   self-scout or scout an opponent.

It trains on free, open nflverse NFL play-by-play, and takes your own Hudl
exports or hand charting so it works for teams that aren't in public datasets.

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

On a fully held-out NFL season the model calls run vs pass correctly 74 percent
of the time when it knows the QB alignment and tempo, and 70 percent from the
situation alone, against 61 percent for always guessing pass. It reports its
calibration (Brier score), not just accuracy, and is validated with a time-based
split: train on past seasons, test on the most recent. A random split would leak
the future and inflate the results.

"Pass" means a called dropback, so scrambles and sacks count as pass. That is
the call a defense has to defend, and it's how nflverse's `qb_dropback` labels
plays. Predicting a specific play family is much harder and is not attempted.

## Project status

| Layer | Status |
|-------|--------|
| Data + ML pipeline (`ml/`) | Working end-to-end on real NFL data |
| API (`api/`) | Working (auth, predict/recommend, tendencies, uploads, vocab) |
| Web app (`web/`) | Working MVP (Vite + React dashboard over the API) |
| Hudl CSV import | Working (breakdown export to plays) |
| Formation/motion vocabulary | Working (canonical vocab + per-team mapping) |
| Deploy | Dockerfiles + docker-compose (Postgres), GitHub Actions CI. Not hosted yet |

### Measured results (run/pass, 2019-2023)

Trained on 173,881 real run/pass plays from nflverse, with a time-split: train on
2019-2021, calibrate on 2022, test on the fully held-out 2023 season (35,474
plays). Reproduce with the quickstart below; the numbers are also saved in
`ml/models/runpass.json`.

| Metric (2023 test season) | Shotgun/no-huddle known | Situation only |
|--------|-------|-------|
| Accuracy | 74.1% | 70.5% |
| Naive baseline (always guess pass) | 61.3% | 61.3% |
| ROC-AUC | 0.816 | 0.785 |
| Brier score (lower is better-calibrated) | 0.169 | 0.181 |

The top signals are what a coordinator reads: shotgun vs under center, yards to
go, clock, down, and score. For example, 3rd-and-8 from the 45 is 97% pass out of
shotgun and 67% under center; 3rd-and-1 at the 2 is 71% run.

The model deliberately uses only inputs a coach can supply before the snap.
Team identity is left out (it learned NFL team names, which mean nothing for your
opponent), and so are formation, personnel, and motion, because public NFL data
doesn't have them. Those come in through the opponent blend instead, from the
film you upload.

## Roadmap

Done:

- **Formation and pre-snap motion tendencies.** A team lines up in Pro Right on
  3rd down and jet-motions the slot, and the tendency matrix says run. Formation
  and motion are captured from Hudl imports and manual charting, folded onto a
  canonical vocabulary (`ml/engage8/vocab.py`) so a team's naming variants
  ("Trips Rt" / "Trips") combine into one bucket. Unrecognized names are surfaced
  for the coach to map per team; mappings apply on read, no re-import needed. Both
  `formation` and `motion` are tendency splits, and they drive the opponent blend
  on the Predict screen.

- **Opponent-specific predictions.** Upload an opponent's film and the
  prediction blends their own tendencies (overall, in that down and distance,
  out of that formation and motion) into the league model, weighted by how many
  plays back each one up. The Predict screen shows every step.

- **Private team workspaces.** Every play, upload, and mapping belongs to one of
  your teams; nobody else can see or query it. Uploads can be listed and
  deleted, and the same file can't be imported twice.

- **Web dashboard.** A Vite + React dashboard (`web/`) over the API: sign in,
  upload breakdowns, browse the tendency matrix, map vocabulary, and run
  predict/recommend in the browser.

Planned next, roughly in priority order:

1. **Picture-based vocabulary matching.** Replace the text mapping UI with a
   grid of formation/motion diagrams a coach clicks to map raw names, so no one
   has to know the canonical spelling. The mapping API and the
   `CanonicalPicker` component are already the seam for this.

2. **Per-coordinator and level-specific models.** The opponent blend adjusts an
   NFL-trained model. With enough charted high school or college film, train a
   base model for that level, and track tendencies per coordinator across seasons.

3. **Hosted deploy.** The Docker images are ready; pick a host (e.g. a managed
   container service + Postgres for the API, static hosting for the dashboard).

## Quickstart

The trained model is committed in `ml/models/`, so the API and dashboard work
without running the pipeline. To run the whole stack in Docker:

```bash
export ENGAGE8_JWT_SECRET=$(openssl rand -hex 32)
docker compose up --build      # web: http://localhost:8080, API: :8000/docs
```

Or run each part locally: see [api/README.md](api/README.md) and
[web/README.md](web/README.md).

### Retrain the model (ML pipeline)

```bash
cd ml
python -m venv .venv && source .venv/bin/activate   # Python 3.11 to 3.14
pip install -r requirements.txt
python -m pytest                                    # tests, no network needed

# 1. Pull nflverse play-by-play (downloads to ml/data/)
python -m engage8.extract --seasons 2019 2020 2021 2022 2023

# 2. Normalize to the canonical schema and engineer features
python -m engage8.features

# 3. Train the run/pass model (time-split, calibrated) into ml/models/
python -m engage8.train

# 4. Predict a situation
python -m engage8.predict --down 2 --distance 6 --yardline 38 \
    --quarter 2 --clock 252 --score-diff 3 --shotgun
```

## Repo layout

```
engage-eight/
├── ml/        # data pipeline, model training, committed model (ml/models/)
├── api/       # FastAPI service (auth, predict, tendencies, uploads, vocab)
└── web/       # Vite + React dashboard
```

## Data sources

- **nflverse / nflfastR** ([github.com/nflverse](https://github.com/nflverse)):
  open NFL play-by-play with EPA and win probability. The pipeline downloads the
  published season parquet files directly, so there's no extra loader dependency.
- **Hudl exports and manual charting**: import any team's plays from a Hudl
  breakdown CSV or a simple charting CSV and run the same tendency engine and
  opponent blend on them.

## License

MIT, see [LICENSE](LICENSE).
