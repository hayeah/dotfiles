"""Non-interactive fuzzy path matcher inspired by fzf extended-search syntax.

Deterministic boolean filter — no scoring, no ranking. Paths are matched
case-insensitively with forward-slash normalization.

Term syntax::

    [!]['][^]<text>[$][']

Expression composition::

    term1 term2       — implicit AND (all terms must match)
    expr | expr       — compound AND (intersection, lower precedence)
    expr ; expr       — union OR (higher precedence)
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


class MatchError(ValueError):
    """Raised when a pattern is malformed."""


# ---------------------------------------------------------------------------
# Word-boundary helpers
# ---------------------------------------------------------------------------

def _is_word_char(ch: str) -> bool:
    """Letter or digit. Underscore is NOT a word char (unlike regex \\w)."""
    return ch.isalpha() or ch.isdigit()


def _has_word_boundary(s: str, idx: int, size: int) -> bool:
    left_ok = idx == 0 or not _is_word_char(s[idx - 1])
    right_ok = idx + size == len(s) or not _is_word_char(s[idx + size])
    return left_ok and right_ok


def contains_word_exact(s: str, needle: str) -> bool:
    """True if *needle* appears in *s* bounded on both sides."""
    if not needle:
        return False
    start = 0
    while start <= len(s) - len(needle):
        idx = s.find(needle, start)
        if idx < 0:
            break
        if _has_word_boundary(s, idx, len(needle)):
            return True
        start = idx + 1
    return False


def contains_word_prefix(s: str, needle: str) -> bool:
    """True if *needle* appears in *s* with a word boundary on the left."""
    if not needle:
        return False
    start = 0
    while start <= len(s) - len(needle):
        idx = s.find(needle, start)
        if idx < 0:
            break
        if idx == 0 or not _is_word_char(s[idx - 1]):
            return True
        start = idx + 1
    return False


# ---------------------------------------------------------------------------
# Term
# ---------------------------------------------------------------------------

@dataclass
class _Term:
    raw: str
    text: str = ""
    anchor_head: bool = False
    anchor_tail: bool = False
    word_prefix: bool = False
    word_exact: bool = False
    neg: bool = False


def _parse_term(raw: str) -> _Term:
    t = _Term(raw=raw)
    p = raw

    # negation
    if p.startswith("!"):
        t.neg = True
        p = p[1:]
        if not p:
            raise MatchError(f"empty term after negation in {raw!r}")

    # word-boundary quotes
    if p.startswith("'"):
        p = p[1:]
        if not p:
            raise MatchError(f"empty term after leading quote in {raw!r}")
        if p.endswith("'"):
            t.word_exact = True
            p = p[:-1]
            if not p:
                raise MatchError(f"empty term in {raw!r}")
        else:
            t.word_prefix = True

    # ./ as ^ anchor
    if p.startswith("./"):
        t.anchor_head = True
        p = p[2:]

    # ^ / $ anchors
    if p.startswith("^"):
        t.anchor_head = True
        p = p[1:]
    if p.endswith("$"):
        t.anchor_tail = True
        p = p[:-1]

    if not p:
        raise MatchError(f"empty term after stripping modifiers in {raw!r}")

    t.text = p.lower().replace("\\", "/")
    return t


def _term_matches(t: _Term, path: str) -> bool:
    # exact path fast path
    if t.anchor_head and t.anchor_tail and not (t.word_exact or t.word_prefix):
        return path == t.text

    sub = path
    if t.anchor_head:
        if not path.startswith(t.text):
            return False
        sub = path[: len(t.text)]
    if t.anchor_tail:
        if not path.endswith(t.text):
            return False
        sub = path[len(path) - len(t.text) :]

    if t.word_exact:
        return contains_word_exact(sub, t.text)
    elif t.word_prefix:
        return contains_word_prefix(sub, t.text)
    else:
        return t.text in sub


# ---------------------------------------------------------------------------
# Matcher protocol
# ---------------------------------------------------------------------------

class Matcher:
    """Base class for matchers."""

    def match(self, paths: list[str]) -> list[str]:
        raise NotImplementedError


@dataclass
class FuzzyMatcher(Matcher):
    """Matches paths against space-separated terms (implicit AND)."""

    pattern: str
    _terms: list[_Term] = field(default_factory=list, repr=False)

    def match(self, paths: list[str]) -> list[str]:
        if not self._terms:
            return list(paths)

        out: list[str] = []
        for path in paths:
            normal = path.lower().replace("\\", "/")
            ok = True
            for term in self._terms:
                m = _term_matches(term, normal)
                if term.neg:
                    m = not m
                if not m:
                    ok = False
                    break
            if ok:
                out.append(path)
        return out


@dataclass
class CompoundMatcher(Matcher):
    """AND — chains matchers sequentially (intersection)."""

    matchers: list[Matcher]

    def match(self, paths: list[str]) -> list[str]:
        current = paths
        for m in self.matchers:
            current = m.match(current)
        return current


@dataclass
class UnionMatcher(Matcher):
    """OR — merges results from all matchers (deduplicated, preserves first-seen order)."""

    matchers: list[Matcher]

    def match(self, paths: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in self.matchers:
            for p in m.match(paths):
                if p not in seen:
                    seen.add(p)
                    out.append(p)
        return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _new_fuzzy_matcher(pattern: str) -> FuzzyMatcher:
    pattern = pattern.strip()
    if not pattern:
        return FuzzyMatcher(pattern=pattern)
    terms = [_parse_term(tok) for tok in pattern.split()]
    return FuzzyMatcher(pattern=pattern, _terms=terms)


def parse_matcher(pattern: str) -> Matcher:
    """Parse a pattern string into a Matcher.

    Operators:
        ``|`` — compound AND (lower precedence, splits first)
        ``;`` — union OR (higher precedence, binds tighter)
    """
    pattern = pattern.strip()

    # pipe = AND (lower precedence — checked first)
    if "|" in pattern:
        parts = pattern.split("|")
        matchers = [parse_matcher(p) for p in parts if p.strip()]
        if not matchers:
            raise MatchError("compound pattern contains no valid patterns")
        if len(matchers) == 1:
            return matchers[0]
        return CompoundMatcher(matchers=matchers)

    # semicolon = OR (higher precedence)
    if ";" in pattern:
        parts = pattern.split(";")
        matchers = [parse_matcher(p) for p in parts if p.strip()]
        if not matchers:
            raise MatchError("union pattern contains no valid patterns")
        if len(matchers) == 1:
            return matchers[0]
        return UnionMatcher(matchers=matchers)

    return _new_fuzzy_matcher(pattern)
