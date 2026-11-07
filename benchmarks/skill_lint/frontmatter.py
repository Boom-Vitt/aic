"""YAML frontmatter reader for SKILL.md.

The Agent Skills specification requires YAML between opening and closing
``---`` lines. This reader accepts the subset those files use: mappings,
single-line flow sequences, quoted scalars, comments, and literal or folded
block scalars. Every scalar stays a string, matching a string-preserving YAML
load rather than YAML 1.1 boolean and number coercion. It is not a general
YAML parser. Line breaks are normalized to ``\\n``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class FrontmatterError(ValueError):
    """The SKILL.md frontmatter is missing or outside the supported subset."""

    def __init__(self, message: str, line: int = 1) -> None:
        self.line = line
        super().__init__(message)


@dataclass(frozen=True)
class ParsedSkill:
    """Frontmatter fields and the markdown body that follows them."""

    fields: dict[str, object]
    field_lines: dict[str, int]
    body: str
    file_lines: int


_KEY = re.compile(r"^([^:\s][^:]*):(.*)$")


def parse_skill_text(text: str) -> ParsedSkill:
    """Parse one SKILL.md document.

    A frontmatter line whose only content is ``---`` closes the header.
    """

    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("SKILL.md must start with YAML frontmatter (---).", 1)
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        raise FrontmatterError("SKILL.md frontmatter is not closed with ---.", 1)
    fields, field_lines, cursor = _mapping(lines, 1, closing, 0)
    while cursor < closing:
        if lines[cursor].strip() and not lines[cursor].lstrip().startswith("#"):
            raise FrontmatterError("Unexpected content after the frontmatter mapping.", cursor + 1)
        cursor += 1
    return ParsedSkill(
        fields=fields,
        field_lines=field_lines,
        body="\n".join(lines[closing + 1 :]),
        file_lines=len(lines),
    )


def _mapping(
    lines: list[str], start: int, end: int, indent: int
) -> tuple[dict[str, object], dict[str, int], int]:
    fields: dict[str, object] = {}
    field_lines: dict[str, int] = {}
    cursor = start
    while cursor < end:
        line = lines[cursor]
        if not line.strip() or line.lstrip().startswith("#"):
            cursor += 1
            continue
        spaces = _indent(line, cursor + 1)
        if spaces < indent:
            break
        if spaces > indent:
            raise FrontmatterError("Frontmatter indentation does not match its mapping.", cursor + 1)
        match = _KEY.match(line[spaces:])
        if match is None:
            raise FrontmatterError("Unsupported frontmatter line.", cursor + 1)
        key = match.group(1).strip()
        if not key:
            raise FrontmatterError("Frontmatter key is empty.", cursor + 1)
        if key in fields:
            raise FrontmatterError(f"Frontmatter key {key!r} is duplicated.", cursor + 1)
        key_line = cursor + 1
        raw = match.group(2).strip()
        if raw.startswith("#"):
            raw = ""
        if raw.startswith((">", "|")):
            value, cursor = _block(lines, cursor, end, spaces, raw)
        elif raw.startswith(("'", '"')):
            value = _quoted(raw, key_line)
            cursor += 1
        elif raw.startswith("["):
            value = _flow_sequence(raw, key_line)
            cursor += 1
        elif raw.startswith("{"):
            raise FrontmatterError("Flow mappings are not supported in skill frontmatter.", key_line)
        elif raw == "":
            value, cursor = _nested_or_empty(lines, cursor, end, spaces)
        else:
            if ": " in raw or raw.endswith(":"):
                raise FrontmatterError("Quote plain values that contain a colon.", key_line)
            parts = [_plain(raw)]
            cursor += 1
            while cursor < end:
                continued = lines[cursor]
                if not continued.strip() or continued.lstrip().startswith("#"):
                    break
                continued_indent = _indent(continued, cursor + 1)
                if continued_indent <= indent:
                    break
                piece = continued.strip()
                if ": " in piece or piece.endswith(":"):
                    raise FrontmatterError("Quote plain values that contain a colon.", cursor + 1)
                parts.append(piece)
                cursor += 1
            value = " ".join(parts)
        fields[key] = value
        field_lines[key] = key_line
    return fields, field_lines, cursor


def _nested_or_empty(
    lines: list[str], key_index: int, end: int, indent: int
) -> tuple[object, int]:
    nxt = key_index + 1
    while nxt < end and (not lines[nxt].strip() or lines[nxt].lstrip().startswith("#")):
        nxt += 1
    if nxt >= end:
        return None, nxt
    nested_indent = _indent(lines[nxt], nxt + 1)
    if nested_indent <= indent:
        return None, key_index + 1
    if _KEY.match(lines[nxt][nested_indent:]) is None:
        raise FrontmatterError("Unsupported nested frontmatter value.", nxt + 1)
    value, _field_lines, cursor = _mapping(lines, nxt, end, nested_indent)
    return value, cursor


def _block(
    lines: list[str], header_index: int, end: int, key_indent: int, header: str
) -> tuple[str, int]:
    style, chomp, explicit = _block_header(header, header_index + 1)
    minimum = key_indent + 1
    content_indent = minimum + explicit - 1 if explicit is not None else None
    cursor = header_index + 1
    while content_indent is None and cursor < end and lines[cursor].strip() == "":
        cursor += 1
    if content_indent is None and cursor < end and lines[cursor].strip():
        spaces = _indent(lines[cursor], cursor + 1)
        if spaces >= minimum:
            content_indent = spaces
    if content_indent is None:
        return "", cursor
    raw: list[str] = []
    while cursor < end:
        line = lines[cursor]
        if line.strip() == "":
            raw.append("")
            cursor += 1
            continue
        spaces = _indent(line, cursor + 1)
        if spaces < content_indent:
            break
        raw.append(line[content_indent:])
        cursor += 1
    trailing = 0
    while raw and raw[-1] == "":
        raw.pop()
        trailing += 1
    text = _join_block(raw, style)
    if chomp == "strip" or not raw:
        return text, cursor
    if chomp == "clip":
        return text + "\n", cursor
    return text + "\n" + ("\n" * trailing), cursor


def _join_block(raw: list[str], style: str) -> str:
    if not raw:
        return ""
    if style == "|":
        return "\n".join(raw)
    parts: list[str] = []
    for index, line in enumerate(raw):
        if index == 0:
            parts.append(line)
            continue
        previous = raw[index - 1]
        if line == "":
            parts.append("\n")
        elif previous == "" or line.startswith(" ") or previous.startswith(" "):
            parts.append(line if previous == "" else "\n" + line)
        else:
            parts.append(" " + line)
    return "".join(parts)


def _block_header(header: str, line: int) -> tuple[str, str, int | None]:
    if not header or header[0] not in ">|":
        raise FrontmatterError("Invalid block scalar header.", line)
    style = header[0]
    chomp = "clip"
    explicit: int | None = None
    index = 1
    while index < len(header) and header[index] in "+-0123456789":
        character = header[index]
        if character in "+-":
            if chomp != "clip":
                raise FrontmatterError("Block scalar repeats its chomp indicator.", line)
            chomp = "keep" if character == "+" else "strip"
        else:
            if explicit is not None:
                raise FrontmatterError("Block scalar repeats its indent indicator.", line)
            explicit = int(character)
            if explicit == 0:
                raise FrontmatterError("Block scalar indent must be from 1 to 9.", line)
        index += 1
    rest = header[index:].strip()
    if rest.startswith("#"):
        rest = ""
    if rest:
        raise FrontmatterError("Invalid block scalar header.", line)
    return style, chomp, explicit


def _quoted(value: str, line: int) -> str:
    quote = value[0]
    characters: list[str] = []
    index = 1
    while index < len(value):
        character = value[index]
        if quote == "'" and character == "'" and index + 1 < len(value) and value[index + 1] == "'":
            characters.append("'")
            index += 2
            continue
        if character == quote:
            rest = value[index + 1 :].strip()
            if rest and not rest.startswith("#"):
                raise FrontmatterError("Trailing characters after a quoted scalar.", line)
            return "".join(characters)
        if quote == '"' and character == "\\":
            if index + 1 >= len(value):
                raise FrontmatterError("Unterminated escape in a double-quoted scalar.", line)
            mapped = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "/": "/"}.get(value[index + 1])
            if mapped is None:
                raise FrontmatterError("Unsupported escape in a double-quoted scalar.", line)
            characters.append(mapped)
            index += 2
            continue
        characters.append(character)
        index += 1
    raise FrontmatterError("Unterminated quoted scalar.", line)


def _flow_sequence(value: str, line: int) -> list[str]:
    body, rest = _take_flow(value, line)
    if rest and not rest.startswith("#"):
        raise FrontmatterError("Trailing characters after a flow sequence.", line)
    inner = body[1:-1].strip()
    if not inner:
        return []
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(inner):
        character = inner[index]
        if quote is not None:
            current.append(character)
            if quote == "'" and character == "'" and index + 1 < len(inner) and inner[index + 1] == "'":
                current.append(inner[index + 1])
                index += 2
                continue
            if character == "\\" and quote == '"':
                if index + 1 >= len(inner):
                    raise FrontmatterError("Unterminated escape in a flow sequence.", line)
                current.append(inner[index + 1])
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in "'\"":
            quote = character
            current.append(character)
        elif character == ",":
            items.append(_flow_item("".join(current), line))
            current = []
        else:
            current.append(character)
        index += 1
    if quote is not None:
        raise FrontmatterError("Unterminated quote in a flow sequence.", line)
    items.append(_flow_item("".join(current), line))
    return items


def _flow_item(raw: str, line: int) -> str:
    value = raw.strip()
    if not value:
        raise FrontmatterError("Flow sequence contains an empty item.", line)
    if value[0] in "'\"":
        return _quoted(value, line)
    if ": " in value or value.endswith(":"):
        raise FrontmatterError("Quote flow items that contain a colon.", line)
    return _plain(value)


def _take_flow(value: str, line: int) -> tuple[str, str]:
    if not value.startswith("["):
        raise FrontmatterError("Expected a flow sequence.", line)
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(value):
        character = value[index]
        if quote is not None:
            if quote == "'" and character == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if character == "\\" and quote == '"':
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in "'\"":
            quote = character
        elif character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return value[: index + 1], value[index + 1 :].strip()
        index += 1
    raise FrontmatterError("Unclosed flow sequence.", line)


def _plain(value: str) -> str:
    comment = value.find(" #")
    if comment != -1:
        value = value[:comment]
    return value.strip()


def _indent(line: str, line_number: int) -> int:
    width = len(line) - len(line.lstrip(" \t"))
    if "\t" in line[:width]:
        raise FrontmatterError("Tabs cannot indent skill frontmatter.", line_number)
    return width
