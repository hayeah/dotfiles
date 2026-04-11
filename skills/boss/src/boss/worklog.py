"""WORKLOG.md parser + append helpers.

A workspace worklog is a structured Markdown file with:

    ---
    status: working
    section: ...
    ...
    ---

    > ## Section header                  (blockquote — mirror of BOSS.md section)
    > - [ ] coarse user-facing checkbox

    ## Todos                             (with optional ### phase headers)
    ## Agent log
    ## Boss log
    ## Evidence
    ## Trouble report

The parser splits on ``## `` headers (same approach as
:mod:`boss.bossdoc`) and reuses :class:`bossdoc.Checkbox` for todo items.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import bossdoc  # noqa: F401 (yaml used in _parse_frontmatter)
from .bossdoc import Checkbox


_HEADER_RE = re.compile(r"^## +(.*?)\s*$", re.MULTILINE)
_SUBHEADER_RE = re.compile(r"^### +(.*?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)

CANONICAL_SECTIONS = [
    "Todos",
    "Agent log",
    "Boss log",
    "Evidence",
    "Trouble report",
]


@dataclass(slots=True)
class TodoPhase:
    label: str | None
    items: list[Checkbox]


@dataclass
class Worklog:
    """Parsed WORKLOG.md."""

    frontmatter: dict = field(default_factory=dict)
    frontmatter_raw: str = ""
    section_quote: str = ""  # verbatim blockquote text, incl. leading `> `
    phases: list[TodoPhase] = field(default_factory=list)
    agent_log: str = ""
    boss_log: str = ""
    evidence: str = ""
    trouble_report: str = ""
    raw_sections: dict[str, str] = field(default_factory=dict)

    @property
    def all_todos(self) -> list[Checkbox]:
        return [item for phase in self.phases for item in phase.items]

    @property
    def progress(self) -> tuple[int, int]:
        todos = self.all_todos
        return sum(1 for t in todos if t.checked), len(todos)

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status", ""))

    @property
    def slug(self) -> str:
        return str(self.frontmatter.get("slug", ""))


class WorklogError(Exception):
    pass


def _parse_frontmatter(raw: str) -> dict:
    """Parse frontmatter leniently.

    Real worklogs often contain unquoted section titles with colons
    (``section: Foo: bar``), which strict YAML rejects. We try
    ``yaml.safe_load`` first and fall back to a naive ``key: value``
    line parser so the CLI never crashes on a slightly-off worklog.
    """
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    # Fallback: parse `key: value` lines.
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_worklog(path: Path) -> Worklog:
    return parse_worklog_text(path.read_text())


def parse_worklog_text(text: str) -> Worklog:
    wl = Worklog()

    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        wl.frontmatter_raw = fm_match.group(1)
        wl.frontmatter = _parse_frontmatter(wl.frontmatter_raw)
        rest = text[fm_match.end():]
    else:
        rest = text

    # Pull off any leading blockquote (mirror of BOSS.md section text).
    wl.section_quote, rest = _extract_leading_blockquote(rest)

    # Section split.
    sections = _split_sections(rest)
    for header, body in sections:
        wl.raw_sections[header] = body
        name = header.strip()
        if name == "Todos":
            wl.phases = _parse_todos(body)
        elif name == "Agent log":
            wl.agent_log = body.strip("\n")
        elif name == "Boss log":
            wl.boss_log = body.strip("\n")
        elif name == "Evidence":
            wl.evidence = body.strip("\n")
        elif name == "Trouble report":
            wl.trouble_report = body.strip("\n")

    return wl


def _extract_leading_blockquote(text: str) -> tuple[str, str]:
    """Peel off a contiguous ``> ...`` block from the start of *text*.

    Leading blank lines are skipped. Returns ``(quote, remaining)``.
    ``quote`` is the exact substring (ending with a trailing newline if it
    had one); ``remaining`` is *text* with the quote removed.
    """
    i = 0
    n = len(text)
    # Skip leading whitespace lines.
    while i < n:
        # end of this line
        j = text.find("\n", i)
        line_end = j if j != -1 else n
        line = text[i:line_end]
        if line.strip() == "":
            i = line_end + 1 if j != -1 else n
            continue
        break
    quote_start = i
    if i >= n or not text[i:].lstrip().startswith(">"):
        # No blockquote — but we may have consumed leading blank lines, so
        # return from the original start.
        return "", text
    # Collect contiguous `^>` lines (allow blank `>`-less lines inside? no —
    # stop at the first non-`>` content line).
    end = i
    while i < n:
        j = text.find("\n", i)
        line_end = j if j != -1 else n
        line = text[i:line_end]
        if line.startswith(">"):
            end = line_end + 1 if j != -1 else n
            i = end
            continue
        if line.strip() == "":
            # blank line — tentatively include it but stop if nothing quoted follows
            blank_end = line_end + 1 if j != -1 else n
            # Peek ahead.
            k = blank_end
            while k < n:
                m = text.find("\n", k)
                l_end = m if m != -1 else n
                nxt = text[k:l_end]
                if nxt.strip() == "":
                    k = l_end + 1 if m != -1 else n
                    continue
                break
            if k < n and text[k:].startswith(">"):
                # More quote follows; include the blank line.
                end = blank_end
                i = blank_end
                continue
            # No more quote — stop before the blank line.
            break
        break
    quote = text[quote_start:end]
    remaining = text[:quote_start] + text[end:]
    # Trim any leading whitespace we consumed before the quote started.
    # Simpler: return remaining as text[end:] since text[:quote_start] is just
    # blanks and doesn't matter for downstream section parsing.
    remaining = text[end:]
    return quote.rstrip("\n"), remaining


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(header, body), ...] for each ``## `` section in *text*."""
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return []
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        nl = text.find("\n", m.start())
        start = nl + 1 if nl >= 0 else len(text)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        out.append((header, body))
    return out


def _parse_todos(body: str) -> list[TodoPhase]:
    """Split a ``## Todos`` body on ``### `` phase headers."""
    sub_matches = list(_SUBHEADER_RE.finditer(body))
    if not sub_matches:
        items = bossdoc.parse_body(body, base_line=0)
        checkboxes = [it for it in items if isinstance(it, Checkbox)]
        if not checkboxes:
            return []
        return [TodoPhase(label=None, items=checkboxes)]

    phases: list[TodoPhase] = []

    # Anything before the first sub-header — parse as a label=None phase
    # only if it contains actual checkboxes.
    pre = body[: sub_matches[0].start()]
    pre_items = [
        it for it in bossdoc.parse_body(pre, base_line=0) if isinstance(it, Checkbox)
    ]
    if pre_items:
        phases.append(TodoPhase(label=None, items=pre_items))

    for i, m in enumerate(sub_matches):
        label = m.group(1).strip()
        start = m.end()
        end = sub_matches[i + 1].start() if i + 1 < len(sub_matches) else len(body)
        chunk = body[start:end]
        if chunk.startswith("\n"):
            chunk = chunk[1:]
        items = [
            it for it in bossdoc.parse_body(chunk, base_line=0)
            if isinstance(it, Checkbox)
        ]
        phases.append(TodoPhase(label=label, items=items))
    return phases


# ---------------------------------------------------------------------------
# Appenders
# ---------------------------------------------------------------------------


def _now_utc_minute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _format_entry(message: str, ts: datetime | None = None) -> str:
    """Format a timestamped dash-bullet line (possibly multi-line)."""
    if ts is None:
        stamp = _now_utc_minute()
    else:
        stamp = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    lines = message.rstrip().splitlines() or [""]
    first = lines[0]
    rest = lines[1:]
    out = f"- {stamp} {first}".rstrip()
    for line in rest:
        out += "\n  " + line
    return out + "\n"


def append_boss_note(
    path: Path, message: str, ts: datetime | None = None
) -> None:
    _append_to_section(path, "Boss log", _format_entry(message, ts))


def append_agent_log(
    path: Path, message: str, ts: datetime | None = None
) -> None:
    _append_to_section(path, "Agent log", _format_entry(message, ts))


def _append_to_section(path: Path, section: str, entry: str) -> None:
    text = path.read_text()
    new_text = _append_to_section_text(text, section, entry)
    path.write_text(new_text)


def _append_to_section_text(text: str, section: str, entry: str) -> str:
    """Append *entry* to ``## <section>`` in *text*, creating it if missing.

    Idempotent in the sense that the function always places the entry at
    the end of the section body (just before the next ``## `` header or
    EOF), with one trailing newline.
    """
    matches = list(_HEADER_RE.finditer(text))
    target: re.Match[str] | None = None
    for m in matches:
        if m.group(1).strip() == section:
            target = m
            break

    if target is not None:
        # Find end of this section (start of next ## header, or EOF).
        # Snap body_start to the start of the line *after* the header —
        # `_HEADER_RE`'s trailing `\s*$` consumes the newline inconsistently
        # (it does when the body is all whitespace, doesn't when a content
        # line follows), so we recompute deterministically.
        idx = matches.index(target)
        nl = text.find("\n", target.start())
        body_start = nl + 1 if nl >= 0 else len(text)
        if idx + 1 < len(matches):
            body_end = matches[idx + 1].start()
        else:
            body_end = len(text)
        body = text[body_start:body_end]
        # `body_start` is just past the matched header line — the `\s*$`
        # in `_HEADER_RE` has already consumed the trailing `\n`. So we
        # must NOT prepend another `\n` here; we rebuild only the body
        # content + trailing blank line.
        content = body.strip("\n")
        entry_stripped = entry.rstrip("\n")
        if content:
            new_content = content + "\n" + entry_stripped
        else:
            new_content = entry_stripped
        if idx + 1 < len(matches):
            new_body = new_content + "\n\n"
        else:
            new_body = new_content + "\n"
        return text[:body_start] + new_body + text[body_end:]

    # Section missing — insert in canonical order.
    return _insert_section_in_order(text, section, entry)


def _insert_section_in_order(text: str, section: str, entry: str) -> str:
    """Create ``## <section>`` and append *entry* as its body."""
    matches = list(_HEADER_RE.finditer(text))
    existing = [m.group(1).strip() for m in matches]
    try:
        pos = CANONICAL_SECTIONS.index(section)
    except ValueError:
        pos = len(CANONICAL_SECTIONS)

    # Find the first existing canonical section that comes after this one.
    insert_before: re.Match[str] | None = None
    for m, name in zip(matches, existing):
        try:
            p = CANONICAL_SECTIONS.index(name)
        except ValueError:
            continue
        if p > pos:
            insert_before = m
            break

    block = f"## {section}\n\n{entry}"

    if insert_before is not None:
        before = text[: insert_before.start()].rstrip("\n")
        after = text[insert_before.start():]
        return before + "\n\n" + block + "\n" + after

    # No later canonical section exists — append at EOF.
    tail = text.rstrip("\n")
    if tail:
        return tail + "\n\n" + block
    return block
