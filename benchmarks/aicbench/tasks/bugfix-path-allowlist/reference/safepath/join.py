def _root_parts(root: str) -> list[str]:
    if not isinstance(root, str) or not root.startswith("/") or "\\" in root:
        raise ValueError("path")
    parts: list[str] = []
    for part in root.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("path")
            parts.pop()
            continue
        parts.append(part)
    return parts


def join_under(root: str, child: str) -> str:
    parts = _root_parts(root)
    if not isinstance(child, str) or child == "" or child.startswith("/") or "\\" in child:
        raise ValueError("path")
    depth = len(parts)
    for part in child.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if len(parts) <= depth:
                raise ValueError("path")
            parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)
