"""BOSS.md parser, slug rules, doneness derivation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Top-level checkbox at column zero. Nested (` ` indented) checkboxes are
# intentionally NOT matched — see SKILL.md "Top-level checkboxes only".
_TOP_CHECKBOX_RE = re.compile(r"^- \[([ xX])\]", re.MULTILINE)
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
