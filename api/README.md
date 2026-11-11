# Engage Eight API

A FastAPI service that wraps the trained model and tendency engine from `../ml`
and exposes them over HTTP, with auth, teams, plays, and CSV charting upload.

## Run it

```bash
cd api
python -m venv .venv && source .venv/bin/activate   # Python 3.11 to 3.14
pip install -r requirements.txt
cp .env.example .env                                # sets ENGAGE8_DEBUG=true for dev

uvicorn app.main:app --reload
```

Then open the interactive docs at http://localhost:8000/docs.

The API serves the model committed in `../ml/models`, so predictions work
without running the ML pipeline. It uses SQLite on disk by default
(`engage8.db`); set `ENGAGE8_DATABASE_URL` to a Postgres URL
(`postgresql+psycopg://...`) for production.

### Configuration and security

- **Fails closed.** `ENGAGE8_DEBUG` defaults to false, and with it false the app
  refuses to start unless `ENGAGE8_JWT_SECRET` is set. Only set
  `ENGAGE8_DEBUG=true` locally.
- **Data isolation.** Every play, upload, opponent, and vocabulary mapping
  belongs to one team, and every team-scoped route checks that you own it
  (others get 404).
- **Passwords** need at least 10 characters.
- **Rate limits** per client IP: signup 10/hour, login 10/minute, predict and
  recommend 120/minute, uploads 30/hour. They are in-process, so with several
  API instances put a shared limiter in front. Set
  `ENGAGE8_TRUST_PROXY_HEADERS=true` only behind your own proxy.
- **Migrations.** The schema is managed by Alembic (`migrations/`) and upgraded
  on startup. To make a schema change: edit `app/db/models.py`, then
  `alembic revision --autogenerate -m "..."`, review it, and commit it.
  A SQLite database created before migrations (plays without a team) is refused
  at startup with instructions; delete it and re-upload.

### Docker

```bash
# from the repo root
docker build -f api/Dockerfile -t engage-eight-api .
docker run -p 8000:8000 -e ENGAGE8_JWT_SECRET=$(openssl rand -hex 32) engage-eight-api
```

`docker compose up` in the repo root runs the API with Postgres and the web app.

## Endpoints

All `/teams/{team_id}/...` routes require auth and ownership of that team.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | no | Liveness check |
| POST | `/auth/signup` | no | Create a user |
| POST | `/auth/login` | no | Get a JWT |
| GET | `/auth/me` | yes | Current user |
| GET/POST | `/teams` | yes | List/create your teams |
| GET | `/teams/{id}` | yes | One team |
| GET/POST | `/teams/{id}/opponents` | yes | Opponents for a team |
| GET/POST | `/teams/{id}/plays` | yes | List (filter by `offense_team`, `opponent_id`, `down`; paged) or add a play |
| DELETE | `/teams/{id}/plays/{play_id}` | yes | Delete a play |
| POST | `/teams/{id}/uploads` | yes | Import a charting or Hudl CSV (max 5 MB). Form fields: `file`, `source` (auto\|charting\|hudl), optional `team` (offense label) and `opponent_id`. Returns rows skipped and why, and unrecognized formation/motion names. The same file twice returns 409 |
| GET | `/teams/{id}/uploads` | yes | List uploads |
| DELETE | `/teams/{id}/uploads/{upload_id}` | yes | Delete an upload and all its plays |
| GET | `/teams/{id}/tendencies` | yes | Tendency matrix by down/dist, zone, formation, motion, quarter, hash (`split`), optionally for one `team` label or `opponent_id` |
| GET | `/teams/{id}/vocab` | yes | Canonical vocabulary, the team's mappings, and still-unmapped raw formation/motion values |
| POST | `/teams/{id}/vocab` | yes | Upsert raw→canonical formation/motion mappings |
| POST | `/predict` | yes | Run/pass probability. Add `team_id` + `offense_team` (and optionally `formation`, `motion_type`) to blend in that opponent's uploaded plays; the response lists each blend step |
| POST | `/recommend` | yes | The prediction plus rules-based defensive call suggestions (no scores attached) |

## Layout

```
api/app/
├── main.py          # app factory, router registration, startup
├── config.py        # settings (env-driven)
├── deps.py          # get_db, get_current_user, owned_team
├── ml.py            # puts ../ml/engage8 on the import path
├── core/            # security.py (bcrypt + JWT), ratelimit.py (per-IP limits)
├── db/              # SQLAlchemy engine, session, models
├── schemas/         # Pydantic request/response models
├── services/        # prediction, opponent blend, recommendation, tendencies, vocab
└── routers/         # auth, teams, plays, predict, tendencies, uploads, vocab
migrations/          # Alembic schema migrations
```

## Smoke test

```bash
python smoke_test.py    # TestClient run over every endpoint, incl. cross-account isolation
```
