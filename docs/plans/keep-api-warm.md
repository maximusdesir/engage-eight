# Plan: keep the API warm

## Problem

Render's free web service sleeps after 15 minutes without traffic, and the
next request waits up to a minute while it boots. The app says "Waking up the
server…" but a recruiter's first impression is still a wait. Neon's free
database also suspends after about 5 idle minutes, which adds roughly a second
to the first query after that (it's most of the ~3 s seen creating a demo).

## Options

1. **Ping `/health` every 10 minutes.** A scheduled GitHub Actions workflow
   (`on: schedule: - cron: "*/10 * * * *"`) running `curl -sf <api>/health`.
   - Render's free tier gives 750 instance hours a month, and one service
     running all month is about 744, so it fits, but only if this is the only
     free service in the workspace.
   - `/health` doesn't touch the database, so Neon still sleeps (and its free
     compute hours aren't used up).
   - GitHub may delay or skip scheduled runs when it's busy, and disables them
     after 60 days without repository activity. An external pinger such as
     UptimeRobot (free, every 5 minutes) is more reliable.
2. **Only around when it matters.** Ping only during the hours people are
   likely to look, or just before sending the link.
3. **Pay for an always-on instance** (Render Starter). No cold starts and no
   pinging.

## Recommendation

Use an external pinger (option 1 with UptimeRobot) while job hunting, and stop
it afterwards. It's free, needs no code, and is easy to undo. If you'd rather
keep everything in the repo, add the GitHub Actions workflow and accept that it
won't be perfectly regular.

## If doing the workflow

- `.github/workflows/keep-warm.yml` with the schedule above, one `curl` step,
  `permissions: {}`, and `if: github.repository == 'maximusdesir/engage-eight'`
  so forks don't ping it.
- Note it in `docs/deploy.md` and say how to turn it off (disable the
  workflow in the Actions tab).
