# Plan: compute tendencies in the database

## Problem

`GET /teams/{id}/tendencies` loads every matching play into Python, builds a
pandas frame, maps formation and motion names through the vocabulary, and
groups it (`api/app/services/tendencies.py`). With the 250-play demo that
takes about 30 ms. It grows with the number of plays, and each request loads
them all again, so a team with tens of thousands of plays would be slow and
memory-hungry on a 512 MB instance.

The opponent blend in `/predict` loads the same plays, but its slow part was
building one pandas frame per play, and that's already fixed (about 460 ms
down to 25 ms for 250 plays).

## When to do it

Not yet. Do it when a real team crosses about 10,000 plays, or if
[storage quotas](storage-quotas.md) allow much more than that. Measure first
with a seeded team (the sample-opponent script can generate a bigger file).

## Options

1. **GROUP BY in SQL.** Down & distance, field zone, quarter, and hash buckets
   become `CASE` expressions, so Postgres returns a few rows per bucket instead
   of every play. Formation and motion need the team's vocabulary mapping, so
   join `vocab_mappings` on the raw value, or keep those two splits in Python
   but select only the two columns they need.
2. **Cache per upload.** Store each upload's tendency rows when it's imported,
   and recompute when vocabulary mappings change. It's fast to read, but the
   cache has to be invalidated, and the opponent and offense filters multiply
   the combinations.

## Recommendation

Option 1 for the four simple splits, and select-two-columns for formation and
motion. It keeps one source of truth, and `engage8.tendencies.tendency_table`
can stay as the reference the tests compare against.

## Steps

1. A test that builds a few hundred plays with known buckets and checks the SQL
   result matches `tendency_table` on the same plays, for every split.
2. Move one split at a time, keeping the response shape.
3. Time it before and after with 20,000 plays.
