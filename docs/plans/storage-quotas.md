# Plan: storage quotas per account

## Problem

Rate limits are per IP per hour, so they slow abuse down but don't bound it.
A normal signed-up account can upload 30 files an hour, each up to 20,000
plays. That's 600,000 rows an hour, and Neon's free tier holds about 0.5 GB,
around two million play rows. Someone patient, or two IPs, could fill the
database in an afternoon, and then the demo stops working for everyone.

Demo accounts are already capped (`ENGAGE8_DEMO_MAX_ACCOUNTS`) and deleted
after 24 hours, so this is about regular accounts.

## Proposal

Hard limits per account, checked before writing:

| Setting | Default | Checked in |
|---|---|---|
| `ENGAGE8_MAX_TEAMS_PER_USER` | 10 | `POST /teams` |
| `ENGAGE8_MAX_PLAYS_PER_TEAM` | 50,000 | `POST /teams/{id}/uploads`, `POST /teams/{id}/plays` |
| `ENGAGE8_MAX_OPPONENTS_PER_TEAM` | 100 | `POST /teams/{id}/opponents` |

50,000 plays is about 70 games of film per team, far past what a high
school staff charts in a season.

## Steps

1. Add the three settings to `api/app/config.py` and `api/.env.example`.
2. A helper in `api/app/deps.py`, e.g. `check_quota(db, model, where, limit, what)`,
   that runs one `SELECT count(*)` and raises 409 with a message such as
   "This team has 50,000 plays, the most one team can hold. Delete an upload to
   make room."
3. For uploads, count the existing plays plus the rows in the new file before
   inserting. The file has already been parsed by then, so the count is known.
4. Tests in `api/tests/test_security.py`: monkeypatch each limit low and check
   the 409 and that nothing was written.
5. Show the message as-is in the web app (it already shows the API's `detail`).

## Not included

Per-account byte quotas or billing. Counting rows is enough at this size.
