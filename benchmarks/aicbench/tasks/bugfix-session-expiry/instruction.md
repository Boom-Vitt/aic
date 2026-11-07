Fix session expiry across the store and the refresh helper.

`sessions.store.valid(session, now)` is true only when `session["revoked"]` is false and `now < session["expires_at"]`. The expiry instant itself is already invalid. `now` and `expires_at` are `int` values. `revoked` is a `bool`. A bad shape raises `ValueError`.

`sessions.tokens.refresh(session, now, ttl)` returns a new dictionary. `ttl` is an `int` greater than 0. If the session is revoked, raise `PermissionError` and do not extend it. Otherwise set `expires_at` to `now + ttl`, not to the old expiry plus `ttl`. Copy the other keys and leave `revoked` false.

Acceptance: `valid({"expires_at": 10, "revoked": False}, 10)` is false, a revoked session cannot be refreshed, and a live refresh at time 10 with ttl 5 expires at 15 even if the old expiry was 100.
