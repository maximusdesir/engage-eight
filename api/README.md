# Engage Eight API

A FastAPI service that wraps the trained model and tendency engine from `../ml`
and exposes them over HTTP, with auth, teams, plays, and CSV charting upload.

## Run it

```bash
cd api
python -m venv .venv && source .venv/bin/activate   # Python 3.11 to 3.14
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Then open the interactive docs at http://localhost:8000/docs.

The API reuses the model trained in `../ml`, so run the ML pipeline first (see
`../ml/README.md`) or the prediction endpoints return 503. It uses SQLite on disk
by default (`engage8.db`); set `ENGAGE8_DATABASE_URL` to a Postgres URL for
production.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | no | Liveness check |
| POST | `/auth/signup` | no | Create a user |
| POST | `/auth/login` | no | Get a JWT |
| GET | `/auth/me` | yes | Current user |
| GET/POST | `/teams` | yes | List/create teams |
| GET | `/teams/{id}` | yes | One team |
| GET/POST | `/teams/{id}/opponents` | yes | Opponents for a team |
| GET/POST | `/plays` | yes | Filter/insert plays |
| POST | `/predict` | no | Run/pass probability for a situation |
| POST | `/recommend` | no | Predicted offense + ranked defensive calls |
| GET | `/tendencies` | no (yes if `team_id` set) | Tendency matrix by down/dist, zone, formation, motion, quarter, hash. Passing `team_id` applies that team's formation/motion vocabulary mapping and requires auth + ownership of that team |
| POST | `/uploads` | yes | Upload a charting or Hudl CSV (max 5 MB) as plays. Form fields: `source` (auto\|charting\|hudl) and optional `team` to label offense_team. Returns any unrecognized formation/motion names for mapping |
| GET | `/teams/{id}/vocab` | yes | Canonical vocabulary, the team's mappings, and still-unmapped raw formation/motion values |
| POST | `/teams/{id}/vocab` | yes | Upsert raw→canonical formation/motion mappings for the team |

## Layout

```
api/app/
├── main.py          # app factory, router registration, startup
├── config.py        # settings (env-driven)
├── deps.py          # get_db, get_current_user
├── core/security.py # bcrypt hashing + JWT
├── db/              # SQLAlchemy engine, session, models
├── schemas/         # Pydantic request/response models
├── services/        # prediction, recommendation, tendencies (reuse ../ml)
└── routers/         # auth, teams, plays, predict, tendencies, uploads
```

## Smoke test

```bash
python smoke_test.py    # spins up a TestClient and exercises every endpoint
```
