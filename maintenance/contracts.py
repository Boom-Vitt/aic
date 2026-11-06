"""Primary-source packets for the optional, checkout-only research maintainer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDocument:
    url: str
    text: str
    sha256: str
    complete: bool
    fetched_at: str


@dataclass(frozen=True)
class Candidate:
    key: str
    url: str
    title: str
    authors: tuple[str, ...]
    published: str
    updated: str
    tier: str
    documents: tuple[SourceDocument, ...]
    discovery_source: str


@dataclass(frozen=True)
class CollectionBatch:
    candidates: tuple[Candidate, ...]
    errors: tuple[str, ...]
    checked_at: str
