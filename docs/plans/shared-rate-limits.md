# Plan: rate limits that survive restarts

## Problem

`api/app/core/ratelimit.py` keeps its counters in the API process's memory.
Render's free tier stops the process after 15 idle minutes, which resets every
counter, and a second instance would keep its own counts. So "10 demo accounts
an hour" really means "10 since the last restart". The demo cap and the
planned [storage quotas](storage-quotas.md) bound the damage, but the limits
themselves are weaker than they look.

## Options

1. **Store counters in Postgres.** A `rate_hits(key, window_start, count)`
   table with an upsert per request. It survives restarts and works across
   instances. It costs a database round trip on every rate-limited request,
   and Neon wakes from suspend for them, which matters for login and predict.
2. **Rate limit at the edge.** Put the API on a custom domain in a Cloudflare
   zone you control (for example `api.yourdomain.com`, proxied to Render) and
   add a Cloudflare rate-limiting rule. The free plan includes one rule, which
   covers `/auth/*`. It costs nothing at runtime and stops abuse before Render.
   It needs a domain (about $10 a year).
3. **Keep in-memory limits, but only for cheap endpoints,** and rely on
   quotas for anything that writes. That's roughly where things stand now.

## Recommendation

If you get a custom domain (it also unlocks [cookie logins](login-tokens.md)),
do option 2 for `/auth/*` and keep the in-memory limits as a second layer.
Without a domain, do option 1 only for `/auth/signup` and `/auth/demo`, the two
endpoints that create accounts and are rarely called.

## Steps for option 1

1. Alembic migration `0003` adding `rate_hits` (key text, window_start
   timestamp, count int, primary key on key and window_start).
2. A `db_rate_limit(name, limit, window)` dependency next to `rate_limit`,
   using `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1 RETURNING count`
   (SQLite supports the same syntax, so tests still run).
3. The startup purge deletes rows older than a day.
4. Tests: the limit holds after `ratelimit.reset()`, which simulates a restart.
