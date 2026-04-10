"""hayeah.core.shortid — short ID generation and prefix resolution."""

from __future__ import annotations

import secrets
from typing import Iterable

ID_ALPHABET = "0123456789abcdefghijkmnpqrstuvwxyz"
_MIN_QUERY_LEN = 3
_MIN_ID_LEN = 3
_MAX_ID_LEN = 8
_MAX_RETRIES = 10


class IDTooShortError(ValueError):
    """Query is shorter than the minimum length."""


class AmbiguousIDError(ValueError):
    """Multiple candidates match the query prefix."""

    def __init__(self, query: str, matches: list[str]) -> None:
        self.query = query
        self.matches = matches
        super().__init__(
            f"ambiguous prefix {query!r}: matches {matches}"
        )


class IDNotFoundError(ValueError):
    """No candidate matches the query."""


def generate(existing: set[str] | frozenset[str]) -> str:
    """Generate a unique short ID not in *existing*.

    Starts at 3 chars, grows up to 8 on collision (10 retries per length).
    Uses ``secrets`` for cryptographic randomness.
    """
    for length in range(_MIN_ID_LEN, _MAX_ID_LEN + 1):
        for _ in range(_MAX_RETRIES):
            buf = secrets.token_bytes(length)
            id_ = "".join(ID_ALPHABET[b % len(ID_ALPHABET)] for b in buf)
            if id_ not in existing:
                return id_
    raise RuntimeError(
        f"could not generate a unique id after exhausting retries (length up to {_MAX_ID_LEN})"
    )


def resolve(query: str, candidates: Iterable[str]) -> str:
    """Resolve a prefix *query* against *candidates*. Case-insensitive.

    Returns the single matching candidate. Raises on ambiguity, no match,
    or too-short query.
    """
    if len(query) < _MIN_QUERY_LEN:
        raise IDTooShortError(
            f"query {query!r} too short (minimum {_MIN_QUERY_LEN} characters)"
        )

    q = query.lower()
    matches: list[str] = []

    for c in candidates:
        if c.lower() == q:
            return c  # exact match — return immediately
        if c.lower().startswith(q):
            matches.append(c)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousIDError(query, matches)
    raise IDNotFoundError(f"no match for {query!r}")
