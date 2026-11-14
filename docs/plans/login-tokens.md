# Plan: login tokens

## Today

Login returns a 24-hour JWT, the web app keeps it in `localStorage`, and sends
it as `Authorization: Bearer`. That's simple and works across the two hosts
(`pages.dev` for the site, `onrender.com` for the API). The tradeoffs:

- **Any script running on the page can read the token.** The main defence is
  not letting scripts in: React escapes everything it renders, nothing uses
  `dangerouslySetInnerHTML`, and `web/public/_headers` now sends a strict
  Content-Security-Policy (scripts only from the site itself).
- **Signing out only forgets the token in this browser.** A copied token keeps
  working until it expires, and there's no way to sign out everywhere.

## Options

1. **httpOnly cookie.** Scripts can't read it. But the site and API are on
   different sites, so the cookie would have to be `SameSite=None`, and Safari
   and Chrome are blocking third-party cookies, so logins would break for many
   visitors. It only works well with a custom domain where the site and API
   are the same site (`app.yourdomain.com` and `api.yourdomain.com`).
   It also needs CSRF protection: `SameSite=Lax` plus checking the `Origin`
   header on writes.
2. **Shorter tokens plus revocation, still in a header.** Add a
   `token_version` column to `users`, put it in the JWT, and reject tokens
   whose version is older. "Sign out everywhere" and password changes bump it.
   Cut the lifetime to a few hours. This works on today's hosting.
3. **Keep it as is.** Reasonable for a portfolio app with no sensitive data,
   given the CSP.

## Recommendation

Do option 2 now if you add password change or account deletion (both need
revocation anyway). Move to option 1 if and when the app gets a custom domain.

## Steps for option 2

1. Migration adding `users.token_version` (int, default 0).
2. `create_access_token` puts `ver` in the payload; `_decode_user` in
   `api/app/deps.py` compares it with the user's current version and returns 401
   if it's older.
3. `POST /auth/logout-all` bumps the version.
4. Lower `access_token_expire_minutes` to something like 8 hours.
5. Tests: a token stops working after logout-all, and an old-version token is 401.
