def refresh(session, now, ttl):
    if type(now) is not int or type(ttl) is not int or ttl <= 0:
        raise ValueError("ttl")
    updated = dict(session)
    updated["revoked"] = False
    updated["expires_at"] = session["expires_at"] + ttl
    return updated
