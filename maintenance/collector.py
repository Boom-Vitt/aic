"""Bounded primary-source discovery; evidence packets are private, never public copies.

Only fixed source roots in sources.json are queried. No classification or workflow
routing occurs here. Cross-process serialization belongs to the trusted controller;
all arXiv requests in this process share a connection lock and completion clock.
"""
from __future__ import annotations

import errno
import hashlib
import http.client
import ipaddress
import json
import multiprocessing
import re
import socket
import ssl
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit

from .contracts import Candidate, CollectionBatch, SourceDocument

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 80000
MAX_CANDIDATES = 3
REQUEST_SECONDS = 15
FETCH_SECONDS = 60
MAX_REDIRECTS = 4
MAX_WORKER_METADATA_BYTES = 64 * 1024
_HOSTS = frozenset({"export.arxiv.org", "arxiv.org", "api.crossref.org", "www.anthropic.com", "www.nature.com", "idp.nature.com"})
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_ID = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})v[1-9]\d*\Z")
_arxiv_lock = threading.Lock()
_arxiv_last_finished: float | None = None


class CollectionError(ValueError):
    """An unavailable or unsafe source cannot establish the requested evidence."""


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: str, now: datetime) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if len(value) == 10:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None or parsed > now or parsed.year < 1991:
            raise ValueError
        return _utc(parsed)
    except (TypeError, AttributeError, ValueError) as exc:
        raise CollectionError("missing, invalid or future source date") from exc


def _dates(published: str, updated: str, now: datetime) -> tuple[str, str]:
    first, last = _date(published, now), _date(updated, now)
    if datetime.fromisoformat(last.replace("Z", "+00:00")) < datetime.fromisoformat(first.replace("Z", "+00:00")):
        raise CollectionError("source revision predates publication")
    return first, last


def _url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) <= 32 or ord(c) >= 127 for c in url) or "\\" in url:
        raise CollectionError("unsafe source URL")
    try:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in _HOSTS or parts.username is not None or parts.password is not None or parts.port not in (None, 443) or parts.fragment:
            raise ValueError
        decoded = unquote(parts.path)
        if "%" in decoded or "\\" in decoded or any(part in (".", "..") for part in decoded.split("/")) or any(ord(c) < 32 for c in decoded):
            raise ValueError
    except ValueError as exc:
        raise CollectionError("unsafe source URL") from exc
    return url


def _public_addresses(host: str) -> tuple[str, ...]:
    # Validate the entire DNS answer before contacting any address; never re-resolve
    # during a connection attempt. Resolver order is retained across public peers.
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = tuple(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or len(addresses) > 16 or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise CollectionError("official host resolved to non-public or excessive addresses")
    return addresses


def _transport_category(exc: Exception) -> str:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "TLS_CERTIFICATE"
    if isinstance(exc, ssl.SSLError):
        return "TLS_HANDSHAKE"
    if isinstance(exc, socket.gaierror):
        return "DNS_LOOKUP(errno=" + str(exc.errno) + ")"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, OSError):
        code = errno.errorcode.get(exc.errno, "OSERROR")
        return code + "(errno=" + str(exc.errno) + ")"
    return type(exc).__name__


class _PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        deadline = time.monotonic() + self.timeout
        addresses = _public_addresses(self.host)
        failures = []
        for index, address in enumerate(addresses):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failures.append("TIMEOUT")
                break
            raw = None
            try:
                # Trying alternate DNS peers establishes this single connection;
                # it never retries an HTTP request or bypasses TLS verification.
                raw = socket.create_connection((address, 443), timeout=remaining / (len(addresses) - index))
                self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
                self.sock.settimeout(max(0.1, deadline - time.monotonic()))
                return
            except ssl.SSLCertVerificationError:
                if raw is not None:
                    raw.close()
                raise
            except OSError as exc:
                if raw is not None:
                    raw.close()
                failures.append(_transport_category(exc))
            except BaseException:
                if raw is not None:
                    raw.close()
                raise
        raise CollectionError("source connection unavailable: " + "; ".join(failures))


def _request_in_process(url: str, *, deadline: float, connection_factory=None) -> tuple[int, dict[str, str], bytes]:
    """Perform HTTP framing inside the killable transport worker."""
    parts = urlsplit(_url(url))
    if connection_factory is None:
        connection_factory = _PinnedHTTPS
    connection = connection_factory(parts.hostname, timeout=min(REQUEST_SECONDS, max(0.1, deadline - time.monotonic())), context=ssl.create_default_context())
    try:
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        connection.request("GET", path, headers={"User-Agent": "AIC-research-maintainer/1.0 (+https://github.com/Boom-Vitt/aic)", "Accept": "application/atom+xml, application/json, text/html", "Accept-Encoding": "identity", "Connection": "close"})
        transport_socket = connection.sock
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        if response.status != 200:
            return response.status, headers, b""
        length = headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_RESPONSE_BYTES):
            raise CollectionError("oversized or invalid source length")
        chunks = []
        size = 0
        while not response.isclosed():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CollectionError("source response deadline exceeded")
            if transport_socket is not None:
                transport_socket.settimeout(min(REQUEST_SECONDS, remaining))
            chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise CollectionError("source payload exceeds bound")
            chunks.append(chunk)
        if length is not None and size != int(length):
            raise CollectionError("partial source response")
        return response.status, headers, b"".join(chunks)
    except (OSError, http.client.HTTPException) as exc:
        raise CollectionError("source transport unavailable: " + _transport_category(exc)) from exc
    finally:
        connection.close()


def _request_worker(channel, url, deadline, connection_factory):
    """Send bounded JSON metadata and raw bytes, never pickled response data."""
    try:
        try:
            status, headers, body = _request_in_process(
                url, deadline=deadline, connection_factory=connection_factory
            )
            metadata = json.dumps(
                {"status": status, "headers": headers, "length": len(body)},
                ensure_ascii=True, separators=(",", ":"),
            ).encode("ascii")
            if len(metadata) > MAX_WORKER_METADATA_BYTES:
                raise CollectionError("source response headers exceed bound")
        except CollectionError as exc:
            metadata = json.dumps({"error": str(exc)[:4096]}, ensure_ascii=True).encode("ascii")
            body = b""
        except Exception as exc:
            metadata = json.dumps(
                {"error": "source transport unavailable: " + _transport_category(exc)},
                ensure_ascii=True,
            ).encode("ascii")
            body = b""
        channel.sendall(len(metadata).to_bytes(4, "big"))
        channel.sendall(metadata)
        channel.sendall(body)
    except OSError:
        # The parent closes its private channel when cancelling the request.
        pass
    finally:
        channel.close()


def _receive_worker_bytes(channel, count, deadline):
    chunks = []
    while count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CollectionError("source response deadline exceeded")
        channel.settimeout(remaining)
        chunk = channel.recv(min(count, 65536))
        if not chunk:
            raise CollectionError("source transport worker ended without a complete response")
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def _request_once(url: str, *, deadline: float) -> tuple[int, dict[str, str], bytes]:
    """Bound DNS through response completion with a safely spawned worker.

    The parent owns the absolute deadline, cancellation and reaping. The trusted
    internal connection factory is passed explicitly so spawn does not depend on
    inherited state; no factory or executable object comes from response IPC.
    """
    _url(url)
    if time.monotonic() >= deadline:
        raise CollectionError("source response deadline exceeded")
    parent, child = socket.socketpair()
    process = multiprocessing.get_context("spawn").Process(
        target=_request_worker, args=(child, url, deadline, _PinnedHTTPS),
        name="aic-source-transport",
    )
    try:
        process.start()
        child.close()
        length = int.from_bytes(_receive_worker_bytes(parent, 4, deadline), "big")
        if not 0 < length <= MAX_WORKER_METADATA_BYTES:
            raise CollectionError("invalid source transport metadata length")
        try:
            metadata = json.loads(_receive_worker_bytes(parent, length, deadline))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise CollectionError("invalid source transport metadata") from exc
        if not isinstance(metadata, dict):
            raise CollectionError("invalid source transport metadata")
        if set(metadata) == {"error"} and isinstance(metadata["error"], str):
            failure = metadata["error"]
            result = None
        elif (
            set(metadata) == {"status", "headers", "length"}
            and type(metadata["status"]) is int
            and 100 <= metadata["status"] <= 999
            and isinstance(metadata["headers"], dict)
            and all(isinstance(key, str) and isinstance(value, str) for key, value in metadata["headers"].items())
            and type(metadata["length"]) is int
            and 0 <= metadata["length"] <= MAX_RESPONSE_BYTES
        ):
            failure = None
            body = _receive_worker_bytes(parent, metadata["length"], deadline)
            result = metadata["status"], metadata["headers"], body
        else:
            raise CollectionError("invalid source transport metadata")
        process.join(max(0, deadline - time.monotonic()))
        if process.is_alive() or time.monotonic() >= deadline:
            raise CollectionError("source response deadline exceeded")
        if process.exitcode != 0:
            raise CollectionError("source transport worker exited unsuccessfully")
        if failure is not None:
            raise CollectionError(failure)
        return result
    except TimeoutError as exc:
        raise CollectionError("source response deadline exceeded") from exc
    except (OSError, RuntimeError, TypeError) as exc:
        raise CollectionError("source transport worker unavailable: " + _transport_category(exc)) from exc
    finally:
        parent.close()
        child.close()
        if process.pid is not None:
            if process.is_alive():
                # Unlike a thread timeout, kill also cancels resolver and TLS
                # work. Reap before returning or releasing the arXiv lock.
                process.kill()
            process.join()
        process.close()


def _request(url: str, *, deadline: float) -> tuple[int, dict[str, str], bytes]:
    global _arxiv_last_finished
    if urlsplit(url).hostname not in ("export.arxiv.org", "arxiv.org"):
        return _request_once(url, deadline=deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not _arxiv_lock.acquire(timeout=remaining):
        raise CollectionError("arXiv connection wait exceeded source deadline")
    try:
        if _arxiv_last_finished is not None:
            delay = 3 - (time.monotonic() - _arxiv_last_finished)
            if delay > 0:
                if delay >= deadline - time.monotonic():
                    raise CollectionError("arXiv rate-limit wait exceeded source deadline")
                time.sleep(delay)
        if time.monotonic() >= deadline:
            raise CollectionError("arXiv rate-limit wait exceeded source deadline")
        try:
            return _request_once(url, deadline=deadline)
        finally:
            _arxiv_last_finished = time.monotonic()
    finally:
        _arxiv_lock.release()


def _query(url: str) -> dict[str, str]:
    try:
        values = parse_qs(urlsplit(url).query, strict_parsing=True, keep_blank_values=True, max_num_fields=6)
        if any(len(value) != 1 for value in values.values()):
            raise ValueError
        return {key: value[0] for key, value in values.items()}
    except ValueError as exc:
        raise CollectionError("invalid publisher redirect parameters") from exc


def _redirect(original: str, current: str, target: str) -> str:
    target = _url(target)
    root, previous, following = urlsplit(original), urlsplit(current), urlsplit(target)
    if root.hostname != "www.nature.com":
        if following.hostname != root.hostname:
            raise CollectionError("cross-host source redirect refused")
        return target
    # Nature's observed anonymous cookie probe is the only cross-host exception.
    # No cookies are retained/sent. The nested URI and return path must identify
    # this exact DOI-derived article, never another article or an arbitrary URL.
    if root.query or not re.fullmatch(r"/articles/s42256-\d{3}-\d{4,6}-[a-z0-9]+", root.path):
        raise CollectionError("publisher redirect requires an approved article")
    query = _query(target)
    if following.hostname == "idp.nature.com":
        if query.get("redirect_uri") != original:
            raise CollectionError("publisher redirect changed the article identity")
        if previous.hostname == "www.nature.com" and following.path == "/authorize":
            if set(query) == {"response_type", "client_id", "redirect_uri"} and query["response_type"] == "cookie" and query["client_id"] == "grover":
                return target
        if previous.hostname == "idp.nature.com" and previous.path == "/authorize" and following.path == "/transit":
            if set(query) == {"redirect_uri", "code"} and re.fullmatch(r"[A-Za-z0-9_-]{4,128}", query["code"]):
                return target
        raise CollectionError("unapproved publisher identity redirect")
    if following.hostname == "www.nature.com" and following.path == root.path:
        if previous.hostname == "www.nature.com" and not query:
            return target
        if previous.hostname == "idp.nature.com" and previous.path == "/transit":
            if set(query) == {"error", "code"} and query["error"] == "cookies_not_supported" and query["code"] == _query(current).get("code"):
                return target
    raise CollectionError("publisher redirect changed the article identity")


def _fetch(url: str, *, kind: str) -> tuple[bytes, str]:
    current = _url(url)
    original_host = urlsplit(current).hostname
    deadline = time.monotonic() + FETCH_SECONDS
    visited = set()
    for _ in range(MAX_REDIRECTS + 1):
        _url(current)
        if current in visited or time.monotonic() >= deadline:
            raise CollectionError("source redirect loop or deadline exceeded")
        visited.add(current)
        status, headers, body = _request(current, deadline=deadline)
        if status in (301, 302, 303, 307, 308):
            location = headers.get("location")
            if not location:
                raise CollectionError("source redirect omitted target")
            current = _redirect(url, current, urljoin(current, location))
            continue
        if status != 200:
            raise CollectionError("source HTTP status " + str(status))
        if urlsplit(current).hostname != original_host:
            raise CollectionError("source redirect did not return to its official article host")
        if len(body) > MAX_RESPONSE_BYTES:
            raise CollectionError("source payload exceeds bound")
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise CollectionError("encoded source response refused")
        mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        accepted = {"html": {"text/html", "application/xhtml+xml"}, "json": {"application/json"}, "xml": {"application/atom+xml", "application/xml", "text/xml"}}[kind]
        if mime not in accepted:
            raise CollectionError("unexpected source content type")
        return body, current
    raise CollectionError("source redirect limit exceeded")


def _xml(body: bytes):
    # UTF-8 only prevents alternate-width encodings from bypassing the DTD scan.
    try:
        text = body.decode("utf-8-sig")
        if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
            raise CollectionError("unsafe XML DTD/entity or encoding")
        if re.search(r'<\?xml[^>]*encoding\s*=\s*[\'\"](?!utf-8[\'\"])[^\'\"]+', text, re.I):
            raise CollectionError("unsupported XML encoding")
        root = ET.fromstring(text)
        if root.tag != _ATOM + "feed":
            raise CollectionError("source is not an Atom feed")
        return root
    except (UnicodeError, ET.ParseError) as exc:
        raise CollectionError("malformed or partial Atom feed") from exc


class _HTML(HTMLParser):
    """Collect visible source regions and metadata, excluding site chrome/code."""
    _void = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
    _skip = frozenset({"script", "style", "nav", "header", "footer", "aside", "button", "form", "svg", "noscript", "template"})

    def __init__(self, body: bytes):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.meta: dict[str, list[str]] = {}
        self.links: list[str] = []
        self.licenses: list[str] = []
        self.canonicals: list[str] = []
        self.regions = {name: [] for name in ("body", "article", "main")}
        self.closed = set()
        self.headings: list[str] = []
        self.structured = []
        self.engineering_team = False
        self.nodes = 0
        self.feed(body.decode("utf-8-sig"))
        self.close()

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 100000 or len(self.stack) >= 256:
            raise CollectionError("source HTML exceeds structural bounds")
        data = dict(attrs)
        if tag == "meta":
            key = data.get("property") or data.get("name")
            if key and data.get("content"):
                self.meta.setdefault(key.lower(), []).append(data["content"].strip())
        if tag in ("a", "link") and data.get("href"):
            if tag == "a" and data["href"] == "/engineering" and "article" in self._active():
                self.engineering_team = True
            if tag == "a" and self._active() and not self._hidden():
                self.links.append(data["href"])
            if "license" in (data.get("rel") or "").split():
                self.licenses.append(data["href"])
            if tag == "link" and "canonical" in (data.get("rel") or "").split():
                self.canonicals.append(data["href"])
        scope = None
        if data.get("data-article-body") == "true":
            scope = "body"
        elif tag == "article" or "ltx_document" in (data.get("class") or "").split():
            scope = "article"
        elif tag == "main":
            scope = "main"
        if tag not in self._void:
            self.stack.append((tag, scope, tag in self._skip, data.get("type") == "application/ld+json"))
        if tag in ("p", "div", "section", "h1", "h2", "h3", "li", "br"):
            self._append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self._void:
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                scope = self.stack[index][1]
                if scope and index == len(self.stack) - 1:
                    self.closed.add(scope)
                del self.stack[index:]
                break
        if tag in ("p", "div", "section", "h1", "h2", "h3", "li"):
            self._append("\n")

    def _hidden(self):
        return any(item[2] for item in self.stack)

    def _active(self):
        return {item[1] for item in self.stack if item[1]}

    def _append(self, text):
        if not self._hidden():
            for scope in self._active():
                self.regions[scope].append(text)

    def handle_data(self, data):
        if self.stack and self.stack[-1][3]:
            try:
                value = json.loads(data)
                self.structured.extend(value if isinstance(value, list) else [value])
            except (ValueError, TypeError):
                pass
        if not self._hidden() and self._active() and any(item[0] in ("h2", "h3") for item in self.stack):
            self.headings.append(data.strip())
        self._append(data)

    def text(self, region):
        text = "".join(self.regions[region])
        return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())

    def value(self, *keys):
        for key in keys:
            if self.meta.get(key):
                return self.meta[key][0]
        return ""

    def article(self):
        for name in ("body", "article", "main"):
            text = self.text(name)
            if text:
                closed = name in self.closed
                if name == "body" and self.regions["article"]:
                    closed = closed and "article" in self.closed
                return text, closed
        return "", False


def _html(body: bytes) -> _HTML:
    try:
        return _HTML(body)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CollectionError("malformed source HTML") from exc


def _document(url: str, text: str, *, metadata: dict, complete: bool, now: datetime, rights=None) -> SourceDocument:
    truncated = len(text) > MAX_TEXT_CHARS
    evidence = "full-method/article text" if complete else "abstract-only or partial source; not full-method evidence"
    packet = "Bibliographic metadata (source supplied):\n" + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    packet += "\nContent rights evidence: " + (json.dumps(rights, ensure_ascii=False, sort_keys=True) if rights else "unknown; no article license observed")
    packet += "\nUse boundary: private evidence; reference-only public citation. No permission to copy inferred from metadata or repository code licenses."
    packet += "\nEvidence boundary: " + evidence
    if truncated:
        packet += "; truncated at text bound"
    packet += "\nSource text:\n" + text[:MAX_TEXT_CHARS]
    return SourceDocument(url=url, text=packet, sha256=hashlib.sha256(packet.encode("utf-8")).hexdigest(), complete=complete and not truncated, fetched_at=_utc(now))


def _identity(title: str, authors: tuple[str, ...]):
    if not title or len(title) > 1000 or not authors or len(authors) > 250 or any(not author or len(author) > 300 for author in authors):
        raise CollectionError("missing or oversized source identity")


def _credit_names(credit: str) -> tuple[str, ...]:
    """Parse only an explicit name list, never a biography or acknowledgments."""
    names = []
    particles = {"de", "del", "da", "di", "van", "von"}
    for part in re.split(r",\s*(?:and\s+)?|\s+and\s+", credit.strip()):
        name = part.strip()
        words = name.split()
        if not words:
            return ()
        # A final full stop is sentence punctuation, except for supplied initials.
        if name.endswith(".") and not re.fullmatch(r"(?:[A-Z]\.)+", words[-1]):
            name = name[:-1]
            words = name.split()
        if len(words) > 8 or any(
            not word or (not word[0].isupper() and word not in particles)
            or any(not (character.isalpha() or character in ".-'’") for character in word)
            for word in words
        ):
            return ()
        names.append(name)
    return tuple(names)


def _byline_authors(text: str) -> tuple[str, ...]:
    match = re.search(r"(?:^|\n)Written by ([^\n]+)", text)
    if not match:
        return ()
    credit = match.group(1)
    # Comma + a lower-case clause is not another capitalized personal credit.
    credit = re.split(r",\s+(?=[a-z])", credit, maxsplit=1)[0]
    # Stop a following prose sentence while retaining dotted personal initials.
    # Ambiguous/unrecognized attributions fail the name-list grammar below.
    credit = re.split(r"(?<=\.)\s+(?=[A-Z][^\s]*\s+(?!(?:and|de|del|da|di|van|von)\b)[a-z])", credit, maxsplit=1)[0]
    collective = re.fullmatch(r"(.+?)\s+and the\s+([a-z][a-z -]*team):\s*(.+)", credit)
    if collective:
        lead = _credit_names(collective.group(1))
        members = _credit_names(collective.group(3))
        if lead and members:
            return lead + (collective.group(2),) + members
        return ()
    return _credit_names(credit)


def _structured_authors(page: _HTML) -> tuple[tuple[str, ...], tuple[str, ...]]:
    people, organizations = [], []
    pending = list(page.structured)
    while pending:
        item = pending.pop(0)
        if not isinstance(item, dict):
            continue
        for key in ("@graph", "mainEntity"):
            nested = item.get(key)
            if isinstance(nested, dict):
                pending.append(nested)
            elif isinstance(nested, list):
                pending.extend(nested)
        if item.get("@type") not in ("Article", "BlogPosting", "NewsArticle"):
            continue
        values = item.get("author", [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if not isinstance(value, dict) or not isinstance(value.get("name"), str):
                continue
            name = value["name"].strip()
            if value.get("@type") == "Person" and name:
                people.append(name)
            elif value.get("@type") == "Organization" or (not value.get("@type") and name == "Anthropic"):
                organizations.append(name)
    return tuple(dict.fromkeys(people)), tuple(dict.fromkeys(organizations))


def _engineering(url: str, now: datetime, discovery: str) -> Candidate:
    body, final = _fetch(url, kind="html")
    if not re.fullmatch(r"/(?:engineering|research)/[A-Za-z0-9-]+/?", urlsplit(final).path):
        raise CollectionError("not an official engineering article URL")
    page = _html(body)
    if urlsplit(final).path.startswith("/research/") and not page.engineering_team:
        raise CollectionError("official research article is not identified as engineering")
    text, closed = page.article()
    title = page.value("og:title", "citation_title")
    published, updated = _dates(page.value("article:published_time"), page.value("article:modified_time") or page.value("article:published_time"), now)
    people, organizations = _structured_authors(page)
    authors = (
        tuple(page.meta.get("citation_author", []))
        or people
        or _byline_authors(page.text("article") or text)
        or tuple(page.meta.get("author", []))
        or organizations
    )
    _identity(title, authors)
    if not text or not page.headings:
        raise CollectionError("engineering source has no article body")
    metadata = {"url": final, "title": title, "authors": authors, "published": published, "updated": updated, "tier": "engineering"}
    rights = {"license_links": page.licenses, "rights": page.meta.get("dc.rights", [])} if page.licenses or page.meta.get("dc.rights") else None
    document = _document(final, text, metadata=metadata, complete=closed, now=now, rights=rights)
    revision = document.sha256
    return Candidate("engineering:" + final + "@" + revision, final, title, authors, published, updated, "engineering", (document,), discovery)


def _arxiv_identity(raw: str) -> str:
    # Legacy Atom IDs are documented HTTP identifiers, not transport URLs. The
    # only tolerated HTTP value is this exact arXiv identifier, converted to HTTPS.
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or parts.netloc != "arxiv.org" or parts.query or parts.fragment or not parts.path.startswith("/abs/"):
        raise CollectionError("invalid arXiv entry identifier")
    identifier = parts.path[5:]
    if not _ARXIV_ID.fullmatch(identifier):
        raise CollectionError("arXiv identifier must preserve an explicit version")
    return identifier


def _arxiv_candidate(entry, now: datetime, discovery: str, errors: list[str]) -> Candidate:
    get = lambda name: (entry.findtext(_ATOM + name) or "").strip()
    identifier = _arxiv_identity(get("id"))
    title = " ".join(get("title").split())
    authors = tuple((author.findtext(_ATOM + "name") or "").strip() for author in entry.findall(_ATOM + "author"))
    _identity(title, authors)
    published, updated = _dates(get("published"), get("updated"), now)
    url = "https://arxiv.org/abs/" + identifier
    metadata = {"url": url, "title": title, "authors": authors, "published": published, "updated": updated, "tier": "preprint", "metadata_rights": "CC0 (arXiv API terms); paper rights separate"}
    text, complete, rights = get("summary"), False, None
    document_url = url
    try:
        body, document_url = _fetch("https://arxiv.org/html/" + identifier, kind="html")
        page = _html(body)
        article, closed = page.article()
        substantial = any(heading.lower() not in ("abstract", "references", "contents") for heading in page.headings if heading)
        if not article or not page.regions["article"] or not substantial:
            raise CollectionError("no full paper text available")
        text, complete = article, closed
        rights = {"license_links": page.licenses, "rights": page.meta.get("dc.rights", [])} if page.licenses or page.meta.get("dc.rights") else None
    except (CollectionError, OSError) as exc:
        document_url = url
        errors.append("arxiv " + identifier + ": " + str(exc))
    if not text:
        raise CollectionError("arXiv source has neither abstract nor article text")
    document = _document(document_url, text, metadata=metadata, complete=complete, now=now, rights=rights)
    return Candidate("arxiv:" + identifier, url, title, authors, published, updated, "preprint", (document,), discovery)


def _journal_candidate(item: dict, now: datetime, discovery: str) -> Candidate:
    if not isinstance(item, dict) or item.get("type") != "journal-article" or "2522-5839" not in item.get("ISSN", []):
        raise CollectionError("Crossref record is not in the approved journal")
    doi = item.get("DOI", "")
    if not isinstance(doi, str) or not re.fullmatch(r"10\.1038/s42256-\d{3}-\d{4,6}-[a-z0-9]+", doi):
        raise CollectionError("Crossref DOI outside approved journal prefix")
    titles = item.get("title", [])
    title = titles[0] if isinstance(titles, list) and titles and isinstance(titles[0], str) else ""
    authors = tuple(" ".join(value for value in (author.get("given", ""), author.get("family", "")) if value) for author in item.get("author", []) if isinstance(author, dict))
    try:
        date = (item.get("published-online") or item.get("published"))["date-parts"][0]
        if len(date) != 3:
            raise ValueError
        published_raw = datetime(*date, tzinfo=timezone.utc).isoformat()
    except (TypeError, ValueError, KeyError) as exc:
        raise CollectionError("Crossref publication date is missing or imprecise") from exc
    deposited = item.get("deposited", {}).get("date-time") or published_raw
    published, updated = _dates(published_raw, deposited, now)
    url = "https://www.nature.com/articles/" + doi.split("/", 1)[1]
    body, final = _fetch(url, kind="html")
    page = _html(body)
    if page.value("citation_article_type").lower() not in ("article", "review"):
        raise CollectionError("publisher does not identify reviewed research article type")
    if page.value("citation_doi").lower() != doi.lower():
        raise CollectionError("publisher DOI differs from Crossref record")
    if page.canonicals:
        if len(set(page.canonicals)) != 1 or _url(urljoin(final, page.canonicals[0])) != url:
            raise CollectionError("publisher canonical differs from Crossref work")
    # Cookie-probe query identifiers are not bibliographic source revisions.
    final = url
    authors = authors or tuple(page.meta.get("citation_author", []))
    title = title or page.value("citation_title", "og:title")
    _identity(title, authors)
    text, closed = page.article()
    if not text:
        raise CollectionError("publisher article text unavailable")
    methods = any(heading.strip().lower() in ("methods", "methodology", "materials and methods") for heading in page.headings)
    metadata = {"url": final, "doi": doi, "title": title, "authors": authors, "published": published, "updated": updated, "tier": "peer-reviewed", "revision_kind": "Crossref metadata deposit plus article content hash; not asserted paper revision", "metadata_rights": "Crossref descriptive metadata generally unrestricted; abstracts may be copyrighted"}
    rights = {"crossref_deposited_license": item.get("license", []), "publisher_license_links": page.licenses, "publisher_rights": page.meta.get("dc.rights", [])}
    document = _document(final, text, metadata=metadata, complete=closed and methods, now=now, rights=rights)
    revision = document.sha256
    return Candidate("doi:" + doi + "@" + revision, final, title, authors, published, updated, "peer-reviewed", (document,), discovery)


def _json(body: bytes):
    try:
        value = json.loads(body)
        if not isinstance(value, dict) or value.get("status") != "ok" or not isinstance(value.get("message"), dict):
            raise ValueError
        return value["message"]
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CollectionError("malformed or unsuccessful Crossref response") from exc


def _sources():
    return json.loads(Path(__file__).with_name("sources.json").read_text(encoding="utf-8"))


def fetch_candidate(url: str, *, now: datetime) -> Candidate:
    """Fetch an explicit approved official article; never synthesize a candidate.

    An incomplete source may be returned for diagnosis. The controller MUST gate
    every document's complete flag before using it for a research record.
    """
    _utc(now)
    parts = urlsplit(_url(url))
    if parts.query:
        raise CollectionError("explicit article query parameters refused")
    if parts.hostname == "www.anthropic.com" and re.fullmatch(r"/(?:engineering|research)/[A-Za-z0-9-]+/?", parts.path):
        return _engineering(url, now, "explicit approved bootstrap")
    if parts.hostname == "arxiv.org" and parts.path.startswith(("/abs/", "/html/")):
        identifier = parts.path.split("/", 2)[2]
        if not _ARXIV_ID.fullmatch(identifier):
            raise CollectionError("explicit arXiv version required")
        endpoint = "https://export.arxiv.org/api/query?" + urlencode({"id_list": identifier, "max_results": 1})
        body, _ = _fetch(endpoint, kind="xml")
        entries = _xml(body).findall(_ATOM + "entry")
        if len(entries) != 1 or _arxiv_identity(entries[0].findtext(_ATOM + "id") or "") != identifier:
            raise CollectionError("arXiv response differs from requested version")
        return _arxiv_candidate(entries[0], now, endpoint, [])
    if parts.hostname == "www.nature.com" and re.fullmatch(r"/articles/s42256-\d{3}-\d{4,6}-[a-z0-9]+", parts.path):
        doi = "10.1038/" + parts.path.rsplit("/", 1)[1]
        endpoint = "https://api.crossref.org/works/" + quote(doi, safe="/")
        body, _ = _fetch(endpoint, kind="json")
        return _journal_candidate(_json(body), now, endpoint)
    raise CollectionError("URL is not an approved article source")


def collect(now: datetime, *, seen: set[str] | None = None, limit: int = 3) -> CollectionBatch:
    """Discover at most three candidates, preserving partial-source diagnostics."""
    checked_at = _utc(now)
    if type(limit) is not int or not 0 <= limit <= MAX_CANDIDATES:
        raise ValueError("limit must be an integer between zero and three")
    if limit == 0:
        return CollectionBatch((), (), checked_at)
    sources = _sources()
    errors: list[str] = []
    candidates: list[Candidate] = []
    known = set(seen or ())

    def retain(candidate):
        if candidate.key in known:
            return
        known.add(candidate.key)
        candidates.append(candidate)
        if not all(document.complete for document in candidate.documents):
            errors.append(candidate.key + ": abstract-only, partial or truncated evidence; ineligible for full-method adoption")

    endpoint = sources["arxiv"]["url"]
    try:
        body, _ = _fetch(endpoint, kind="xml")
        entries = _xml(body).findall(_ATOM + "entry")
        if len(entries) > MAX_CANDIDATES:
            errors.append("arxiv: response exceeds requested candidate count")
        for entry in entries[:MAX_CANDIDATES]:
            try:
                identifier = _arxiv_identity(entry.findtext(_ATOM + "id") or "")
                if "arxiv:" + identifier not in known:
                    retain(_arxiv_candidate(entry, now, endpoint, errors))
            except (CollectionError, OSError, TypeError, AttributeError) as exc:
                errors.append("arxiv entry: " + str(exc))
    except (CollectionError, OSError) as exc:
        errors.append("arxiv: " + str(exc))

    endpoint = sources["crossref"]["url"]
    try:
        body, _ = _fetch(endpoint, kind="json")
        items = _json(body).get("items")
        if not isinstance(items, list):
            raise CollectionError("Crossref work-list items missing")
        if len(items) > MAX_CANDIDATES:
            errors.append("crossref: response exceeds requested candidate count")
        for item in items[:MAX_CANDIDATES]:
            try:
                retain(_journal_candidate(item, now, endpoint))
            except (CollectionError, OSError, TypeError, AttributeError) as exc:
                errors.append("crossref entry: " + str(exc))
    except (CollectionError, OSError) as exc:
        errors.append("crossref: " + str(exc))

    endpoint = sources["engineering"]["url"]
    try:
        body, final = _fetch(endpoint, kind="html")
        page = _html(body)
        if "main" not in page.closed:
            raise CollectionError("engineering index missing complete main region")
        links = []
        for link in page.links:
            target = urljoin(final, link)
            parts = urlsplit(target)
            if parts.hostname == "www.anthropic.com" and re.fullmatch(r"/(?:engineering|research)/[A-Za-z0-9-]+/?", parts.path) and not parts.query and not parts.fragment and target not in links:
                links.append(target)
        for target in links[:MAX_CANDIDATES]:
            try:
                retain(_engineering(target, now, endpoint))
            except (CollectionError, OSError) as exc:
                errors.append("engineering entry: " + str(exc))
    except (CollectionError, OSError) as exc:
        errors.append("engineering: " + str(exc))
    candidates.sort(key=lambda candidate: (all(document.complete for document in candidate.documents), candidate.updated, candidate.key), reverse=True)
    return CollectionBatch(tuple(candidates[:limit]), tuple(errors), checked_at)
