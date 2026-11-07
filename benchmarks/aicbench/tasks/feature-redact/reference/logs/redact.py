def redact(text, secrets) -> str:
    if not isinstance(text, str) or not isinstance(secrets, list):
        raise TypeError("redact")
    ordered = []
    for secret in secrets:
        if not isinstance(secret, str):
            raise TypeError("secret")
        if secret != "":
            ordered.append(secret)
    ordered.sort(key=len, reverse=True)
    chunks = []
    index = 0
    while index < len(text):
        match = next((secret for secret in ordered if text.startswith(secret, index)), None)
        if match is None:
            chunks.append(text[index])
            index += 1
            continue
        chunks.append("[REDACTED]")
        index += len(match)
    return "".join(chunks)
