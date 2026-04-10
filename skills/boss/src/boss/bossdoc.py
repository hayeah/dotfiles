"""BOSS.md parser, slug rules, doneness derivation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_HEADER_RE = re.compile(r"^## +(.*?)\s*$", re.MULTILINE)
_LEADING_X_RE = re.compile(r"^\[[xX ]\]\s*")

# Line-level patterns for body parsing.
_TOP_CB_RE = re.compile(r"^- \[([ xX])\] (.*)$")
_NESTED_RE = re.compile(r"^([ \t]+)- (.*)$")
_NESTED_CB_RE = re.compile(r"^[ \t]+- \[[ xX]\]")


@dataclass(slots=True)
class Checkbox:
    checked: bool
    text: str
    nested: list[str]
    line: int


@dataclass(slots=True)
class Prose:
    text: str
    line: int


@dataclass
class Section:
    header: str
    body: str
    slug: str
    header_line: int = 0
    items: list[Checkbox | Prose] = field(default_factory=list)

    def has_pending(self) -> bool:
        """True if any unticked top-level checkbox exists."""
        found_any = False
        for item in self.items:
            if isinstance(item, Checkbox):
                found_any = True
                if not item.checked:
                    return True
        return False if found_any else False

    def is_spec_only(self) -> bool:
        """True if all pending checkboxes are spec:-prefixed."""
        pending = [
            item for item in self.items
            if isinstance(item, Checkbox) and not item.checked
        ]
        if not pending:
            return False
        return all(t.text.lower().startswith("spec:") for t in pending)

    def find_nested_checkboxes(self) -> list[str]:
        """Return indented checkbox lines (which has_pending ignores)."""
        lines: list[str] = []
        for item in self.items:
            if isinstance(item, Checkbox):
                for n in item.nested:
                    if _NESTED_CB_RE.match(n):
                        lines.append(n)
        return lines


def slugify(header: str) -> str:
    """Map a section header to a stable kebab-case slug.

    Steps: strip a legacy `[x]` / `[ ]` prefix, lowercase, replace runs of
    non-alphanumerics with `-`, strip leading/trailing `-`.
    """
    s = header.strip()
    s = _LEADING_X_RE.sub("", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


# --- Standalone wrappers (backward compat, accept section_body str) ---

def has_pending(section_body: str) -> bool:
    """True if the section has any unticked top-level `- [ ]` checkbox."""
    items = parse_body(section_body, base_line=0)
    found_any = False
    for item in items:
        if isinstance(item, Checkbox):
            found_any = True
            if not item.checked:
                return True
    return False if found_any else False


def is_spec_only(section_body: str) -> bool:
    """True if all pending (unticked) top-level checkboxes are `spec:` prefixed."""
    items = parse_body(section_body, base_line=0)
    pending = [
        item for item in items
        if isinstance(item, Checkbox) and not item.checked
    ]
    if not pending:
        return False
    return all(t.text.lower().startswith("spec:") for t in pending)


def find_nested_checkboxes(section_body: str) -> list[str]:
    """Return any indented checkbox lines (which `has_pending` ignores)."""
    items = parse_body(section_body, base_line=0)
    lines: list[str] = []
    for item in items:
        if isinstance(item, Checkbox):
            for n in item.nested:
                if _NESTED_CB_RE.match(n):
                    lines.append(n)
    return lines


def parse_body(text: str, base_line: int) -> list[Checkbox | Prose]:
    """Parse section body text into a list of Checkbox and Prose items."""
    items: list[Checkbox | Prose] = []
    lines = text.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        m = _TOP_CB_RE.match(raw)
        if m:
            checked = m.group(1) != " "
            cb_text = m.group(2)
            nested: list[str] = []
            j = i + 1
            while j < n:
                if _NESTED_RE.match(lines[j]):
                    nested.append(lines[j])
                    j += 1
                else:
                    break
            items.append(Checkbox(
                checked=checked,
                text=cb_text,
                nested=nested,
                line=base_line + i,
            ))
            i = j
        else:
            # Skip blank lines between items; collect contiguous prose.
            stripped = raw.strip()
            if not stripped:
                i += 1
                continue
            prose_start = i
            prose_lines: list[str] = [raw]
            j = i + 1
            while j < n:
                if _TOP_CB_RE.match(lines[j]):
                    break
                prose_lines.append(lines[j])
                j += 1
            # Trim trailing blank lines from prose block.
            while prose_lines and not prose_lines[-1].strip():
                prose_lines.pop()
            if prose_lines:
                items.append(Prose(
                    text="\n".join(prose_lines),
                    line=base_line + prose_start,
                ))
            i = j
    return items


def parse_sections(text: str) -> list[Section]:
    """Split BOSS.md into top-level `## ` sections.

    Content before the first `## ` is dropped (it's the doc preamble /
    `# Title`). Each section's body extends to the next `## ` or EOF.
    """
    matches = list(_HEADER_RE.finditer(text))
    # Pre-compute line number at each offset.
    line_at = _build_line_index(text)
    sections: list[Section] = []
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        header_line = line_at(m.start())
        # base_line for body items: header_line + 1 (body starts on line after header)
        body_base = header_line + 1
        items = parse_body(body, base_line=body_base)
        sections.append(Section(
            header=header,
            body=body,
            slug=slugify(header),
            header_line=header_line,
            items=items,
        ))
    return sections


def _build_line_index(text: str):
    """Return a closure that maps byte offset → 1-based line number."""
    # Build sorted list of line-start offsets.
    starts = [0]
    pos = 0
    for ch in text:
        pos += 1
        if ch == "\n":
            starts.append(pos)

    def line_at(offset: int) -> int:
        # Binary search for the line containing offset.
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) >> 1
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1  # 1-based
    return line_at


_DATE_HEADER_RE = re.compile(r"^# +(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


class BossDocError(Exception):
    pass


def load(path: Path) -> list[Section]:
    """Read + parse BOSS.md, raising BossDocError on duplicate slugs."""
    if not path.exists():
        raise BossDocError(f"BOSS.md not found at {path}")
    text = path.read_text()
    sections = parse_sections(text)
    seen: dict[str, str] = {}
    dups: list[tuple[str, str]] = []
    for s in sections:
        if s.slug in seen:
            dups.append((s.slug, s.header))
        else:
            seen[s.slug] = s.header
    if dups:
        lines = ["duplicate slugs in BOSS.md:"]
        for slug, header in dups:
            lines.append(f"  {slug!r}: {header!r} (also: {seen[slug]!r})")
        raise BossDocError("\n".join(lines))
    return sections


def append_section(path: Path, section_text: str, date: str) -> str:
    """Append *section_text* to the boss doc under a ``# <date>`` group.

    If a ``# <date>`` header already exists, the section is appended at the
    end of that date group (before the next ``# `` header or EOF).  Otherwise
    a new ``# <date>`` header is created at the end of the file.

    Returns the slug of the newly added section.

    Raises ``BossDocError`` if *section_text* contains no ``## `` header or
    if the resulting slug would duplicate an existing section.
    """
    section_text = section_text.strip()
    if not section_text:
        raise BossDocError("section text is empty")

    header_m = _HEADER_RE.search(section_text)
    if header_m is None:
        raise BossDocError("section text must contain a ## header")

    new_slug = slugify(header_m.group(1))

    # Validate no duplicate slug.
    if path.exists():
        existing = parse_sections(path.read_text())
        for s in existing:
            if s.slug == new_slug:
                raise BossDocError(
                    f"slug {new_slug!r} already exists (header: {s.header!r})"
                )

    # Ensure section_text ends with a newline.
    if not section_text.endswith("\n"):
        section_text += "\n"

    if not path.exists():
        path.write_text(f"# {date}\n\n{section_text}")
        return new_slug

    text = path.read_text()

    # Find the date group for the given date.
    date_matches = list(_DATE_HEADER_RE.finditer(text))
    target = None
    for m in date_matches:
        if m.group(1) == date:
            target = m
            break

    if target is not None:
        # Find the end of this date group: the next `# ` header (level 1) or EOF.
        # A level-1 header is `^# ` that is NOT `^## `.
        next_date_pos = len(text)
        for m in date_matches:
            if m.start() > target.start():
                next_date_pos = m.start()
                break

        # Insert at the end of the date group (before the next date header).
        insert_pos = next_date_pos
        # Ensure spacing.
        before = text[:insert_pos].rstrip("\n")
        after = text[insert_pos:]
        if after:
            text = before + "\n\n" + section_text + "\n" + after
        else:
            text = before + "\n\n" + section_text
    else:
        # No existing date group — append a new one at the end.
        text = text.rstrip("\n") + "\n\n# " + date + "\n\n" + section_text

    path.write_text(text)
    return new_slug
