import base64
import binascii


def encode_cursor(offset: int) -> str:
    if type(offset) is not int:
        raise TypeError("offset")
    if offset < 0:
        raise ValueError("offset")
    raw = base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")
    return raw.rstrip("=")


def decode_cursor(token: str) -> int:
    if not isinstance(token, str) or token == "" or "=" in token or any(character.isspace() for character in token):
        raise ValueError("cursor")
    padded = token + "=" * (-len(token) % 4)
    try:
        text = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True).decode("ascii")
    except (binascii.Error, ValueError, UnicodeError):
        raise ValueError("cursor") from None
    if text != "0" and (not text.isdigit() or text.startswith("0")):
        raise ValueError("cursor")
    if not text.isdigit():
        raise ValueError("cursor")
    return int(text)


def page(items, *, limit, cursor=None):
    if type(items) is not list or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("page")
    offset = 0 if cursor is None else decode_cursor(cursor)
    window = list(items[offset:offset + limit])
    next_offset = offset + limit
    next_cursor = None if next_offset >= len(items) else encode_cursor(next_offset)
    return {"items": window, "next_cursor": next_cursor}
