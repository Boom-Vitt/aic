def _parts(path: str) -> list[str] | None:
    if not isinstance(path, str) or not path.startswith("/") or "\\" in path:
        return None
    parts: list[str] = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return parts


def is_within(root: str, candidate: str) -> bool:
    root_parts = _parts(root)
    candidate_parts = _parts(candidate)
    if root_parts is None or candidate_parts is None:
        return False
    return candidate_parts[:len(root_parts)] == root_parts
