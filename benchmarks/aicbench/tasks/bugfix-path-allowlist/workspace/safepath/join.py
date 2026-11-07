def join_under(root: str, child: str) -> str:
    if not isinstance(root, str) or not isinstance(child, str) or not root.startswith("/"):
        raise ValueError("path")
    if child.startswith("/"):
        return child
    return root.rstrip("/") + "/" + child
