# Engage Eight

Engage Eight predicts whether a football offense will run or pass before the
snap, and shows a defense what an opponent likes to do in each situation.

I play defense, and watching scout film is slow. The players I grew up watching,
Luke Kuechly, Peyton Manning, Tom Brady, Ray Lewis, stood out because they knew
what was coming before the ball was snapped. I wanted a tool that does some of
that film work for me and lets me check my own pre-snap reads. I also think AI
is going to change how teams scout, and I wanted to see how far one person could
get with free data and no budget.

## What it does

- Predicts run or pass from the down, distance, field position, clock, score,
  and whether the QB is in shotgun. 3rd and 8 from the 45 out of shotgun comes
  back 97% pass. Under center, 67%.
- Builds tendency tables from a team's film. Upload a Hudl export or a
  hand-charted CSV and see their run/pass split by down and distance, field
  zone, formation, motion, quarter, and hash.
- Adjusts the prediction for the opponent you're actually playing. If you've
  uploaded their film, it shifts toward what they do in that spot, and shows how
  many plays it's leaning on so you can tell 4 plays from 40.
- Suggests a few defensive calls for the situation. These come from written
  rules, not the model, and the app labels them that way.

## Results

Trained on NFL plays from 2019 to 2021, calibrated on 2022, and tested on all
35,474 plays of the 2023 season, which the model never saw.

| | Accuracy | AUC | Brier |
|---|---|---|---|
| With shotgun and tempo known | 74.1% | 0.816 | 0.169 |
| Down, distance, clock, score only | 70.5% | 0.785 | 0.181 |
| Always guess pass | 61.3% | | |

A few decisions behind those numbers:

- The test set is a whole later season, not a random sample. A random split
  lets the model see other plays from the same games and makes it look better
  than it is.
- "Pass" means a called pass, so scrambles and sacks count. That's the play the
  defense has to stop.
- The model only uses what a coach can know before the snap. An earlier version
  leaned on NFL team names, which don't help when you're scouting a high school
  team, so I took them out. Accuracy went up slightly.

## How it's built

- `ml/`: Python, pandas, LightGBM with isotonic calibration. Pulls nflverse
  play-by-play, builds features, trains the model, and reads Hudl and charting
  CSVs.
- `api/`: FastAPI, SQLAlchemy, and Alembic, on Postgres (SQLite locally). JWT
  auth, and each coach's uploads are private to their team.
- `web/`: React and TypeScript with Vite.
- Docker Compose runs the whole stack. GitHub Actions runs the tests and builds
  the images on every push.

## Run it

The trained model is checked in, so you don't need to train anything first.

```bash
export ENGAGE8_JWT_SECRET=$(openssl rand -hex 32)
docker compose up --build
```

Open http://localhost:8080. API docs are at http://localhost:8000/docs.

To run the pieces without Docker, see [api/README.md](api/README.md) and
[web/README.md](web/README.md). To retrain the model:

```bash
cd ml
pip install -r requirements.txt
python -m pytest
python -m engage8.extract --seasons 2019 2020 2021 2022 2023
python -m engage8.features
python -m engage8.train
python -m engage8.predict --down 3 --distance 8 --yardline 45 --shotgun
```

More detail on the pipeline is in [ml/README.md](ml/README.md).

## What's next

- Let coaches map their formation names by clicking a diagram instead of
  picking from a list.
- Train on high school and college film once I have enough of it. Right now the
  opponent adjustment sits on top of an NFL model.
- Host it somewhere coaches can sign up and use it.

## Data and license

Play-by-play data comes from [nflverse](https://github.com/nflverse). MIT
license, see [LICENSE](LICENSE).
