def valid(session, now) -> bool:
    if not isinstance(session, dict) or type(now) is not int:
        raise ValueError("session")
    expires_at = session.get("expires_at")
    revoked = session.get("revoked")
    if type(expires_at) is not int or type(revoked) is not bool:
        raise ValueError("session")
    return (not revoked) and now < expires_at
