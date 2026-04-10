"""BOSS.md parser, slug rules, doneness derivation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Top-level checkbox at column zero. Nested (` ` indented) checkboxes are
# intentionally NOT matched — see SKILL.md "Top-level checkboxes only".
_TOP_CHECKBOX_RE = re.compile(r"^- \[([ xX])\]", re.MULTILINE)
_TOP_CHECKBOX_LINE_RE = re.compile(r"^- \[([ xX])\] (.*)$", re.MULTILINE)
_NESTED_CHECKBOX_RE = re.compile(r"^[ \t]+- \[[ xX]\]", re.MULTILINE)
_HEADER_RE = re.compile(r"^## +(.*?)\s*$", re.MULTILINE)
_LEADING_X_RE = re.compile(r"^\[[xX ]\]\s*")


@dataclass
class Section:
    header: str
    body: str
    slug: str


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


def has_pending(section_body: str) -> bool:
    """True if the section has any unticked top-level `- [ ]` checkbox.

    A section with no top-level checkboxes is treated as done (pure prose).
    Nested checkboxes are silently ignored — `boss doctor` warns about them.
    """
    boxes = _TOP_CHECKBOX_RE.findall(section_body)
    if not boxes:
        return False
    return any(b == " " for b in boxes)


def is_spec_only(section_body: str) -> bool:
    """True if all pending (unticked) top-level checkboxes are `spec:` prefixed.

    Returns False if there are no pending checkboxes at all.
    """
    pending = [
        text for check, text in _TOP_CHECKBOX_LINE_RE.findall(section_body)
        if check == " "
    ]
    if not pending:
        return False
    return all(t.lower().startswith("spec:") for t in pending)


def find_nested_checkboxes(section_body: str) -> list[str]:
    """Return any indented checkbox lines (which `has_pending` ignores)."""
    return _NESTED_CHECKBOX_RE.findall(section_body)


def parse_sections(text: str) -> list[Section]:
    """Split BOSS.md into top-level `## ` sections.

    Content before the first `## ` is dropped (it's the doc preamble /
    `# Title`). Each section's body extends to the next `## ` or EOF.
    """
    matches = list(_HEADER_RE.finditer(text))
    sections: list[Section] = []
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append(Section(header=header, body=body, slug=slugify(header)))
    return sections


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
