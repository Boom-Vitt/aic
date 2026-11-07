def valid(session, now) -> bool:
    if type(now) is not int or type(session.get("expires_at")) is not int or type(session.get("revoked")) is not bool:
        raise ValueError("session")
    return (not session["revoked"]) and now <= session["expires_at"]
