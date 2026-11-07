def refresh(session, now, ttl):
    if not isinstance(session, dict) or type(now) is not int or type(ttl) is not int or ttl <= 0:
        raise ValueError("ttl")
    revoked = session.get("revoked")
    if revoked is True:
        raise PermissionError("revoked")
    if revoked is not False or type(session.get("expires_at")) is not int:
        raise ValueError("session")
    updated = dict(session)
    updated["expires_at"] = now + ttl
    updated["revoked"] = False
    return updated
