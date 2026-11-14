# Follow-up plans

Changes that came out of the November 2026 security and performance review and
are too big to make without a decision first. The small fixes from that review
are already in (body-size limit, field limits, PyJWT, CSP and security headers,
login timing, faster opponent blend; see the commit history).

In rough priority order:

| Plan | Why it matters | Size |
|---|---|---|
| [Storage quotas](storage-quotas.md) | One signed-up account can still fill the free 0.5 GB database over a few days. | Small to medium |
| [Keep the API warm](keep-api-warm.md) | A recruiter's first click can wait up to a minute for Render to wake. | Small, but a hosting decision |
| [Shared rate limits](shared-rate-limits.md) | Limits live in memory and reset every time Render restarts the API. | Medium |
| [Login tokens](login-tokens.md) | The token sits in `localStorage`, readable by any script that gets onto the page. | Medium to large; needs a custom domain |
| [Tendencies in SQL](tendencies-in-sql.md) | Tendencies load every play into pandas on each request. Fine now, slow at 10,000+ plays per team. | Medium; do it when it's slow |
