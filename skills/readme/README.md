---
name: readme
description: Write one canonical README.md per directory — always with SKILL-compat frontmatter (name + description) and always symlinked as SKILL.md. The README saturates normal-use needs for the directory and everything in it; sub-docs are read on demand, only when the reader needs more detail than the README provides. Use when creating a new README or updating one after code changes.
---

# readme

One canonical entry-point doc per directory: `README.md`. `SKILL.md` is always a symlink to `README.md` — never a second real file. Every README carries YAML frontmatter (`name` + `description`) at the top — the SKILL-compat header — so any directory is discoverable as a skill without a separate decision about which ones "count."

**The README saturates normal-use needs** for the directory and everything it contains. When a directory has sub-docs (or sub-modules, sub-skills, sub-guides), the README absorbs enough of each of them — concept, minimal usage, inline pointer — that the reader only follows a sub-doc link when they need overflow detail (full API reference, edge cases, design rationale). The README is the primary layer; sub-docs are the second layer, read on demand.

## TLDR

- File layout per directory:
  ```
  foo/
    README.md       # real file — frontmatter + body that absorbs the sub-tree
    SKILL.md        # symlink → README.md
  ```
- Document skeleton, top to bottom:
  ```
  ---
  name: foo                # always — matches the directory name
  description: one line, what + when
  ---

  # foo

  <short orientation — 1–3 lines, the 30-second pitch of the directory>

  ## <first sub-item or body section>
  self-contained digest: concept + minimal usage, then an inline
  `-> [spec](path/to/deeper-doc)` pointer for overflow detail

  ## <next sub-item or body section>
  ...
  ```
- Create the symlink in the same commit as the README:
  ```bash
  cd <dir>
  ln -s README.md SKILL.md
  ```

## The saturation principle

- The whole README is a self-contained intro to the directory and its sub-tree. Readers should be able to do a normal task without clicking through.
- Deeper sub-docs (full specs, reference APIs, design rationale) stay as separate files, but the README *absorbs* enough of each that the link is only followed when extra detail is genuinely needed.
- If you find yourself writing "see X for details" as the only coverage of a sub-thing, the README is under-absorbing. Pull the normal-use surface — one paragraph, one usage block — into the README and keep `-> [spec](X)` as the overflow pointer.

### For a leaf directory (one tool, one skill, one concept)

The README documents the one thing end-to-end: short orientation, usage, any reference the reader needs. No internal fan-out.

### For a hub directory (a library, a skill collection, a repo root with many sub-docs)

The body is per-sub-item digests. Each sub-item gets a `##` section containing:

- A one- or two-paragraph description — concept + any quirks a normal user needs to know.
- A minimal copy-pasteable usage example (per language, if multi-language).
- A trailing `-> [spec](path/to/sub-doc/)` link (or several, pipe-separated) pointing at the deeper reference for overflow detail.

Sketch:

```markdown
## logger — Structured Logging

Colored console output + JSONL file log. `LOG_LEVEL` (debug/info/warn/error,
default info) controls verbosity.

    from hayeah.core.logger import new
    log = new("my-tool")
    log.info("starting", port=8080)

-> [spec](path/to/logger/)

## fzfmatch — Fuzzy Path Matcher
...
```

A reader can use the sub-thing from the README alone; they only click through to the spec when they need the full API or design rationale.

### For a big catalog (many sub-things across categories, where per-item digests don't fit)

When the fan-out grows past what you can digest in full — say 15+ entries spread across categories — compress to a catalog. Each entry collapses to a link plus a terse pair of labelled hooks:

```markdown
## <Category>

- [<full/path/to/doc>](<full/path/to/doc>)
  - what: <what it is and what it does — 20–30 words>
  - when: <situations that should send an agent here — 20–30 words>
```

- Flat list within a category. A skill and its sub-guides are siblings, not nested children. The only nested bullets are `what:` and `when:`.
- `what`: the "is" half identifies the kind (library, CLI, style guide, design doc); the "does" half names the capability.
- `when`: concrete decision triggers. Drop the generic "Use when…" preamble; lead with the actual moment of need.
- 20–30 words each — shorter is too sparse, longer means the hook is doing the linked doc's job.
- Sentence-case. No trailing period on `what`/`when` lines.
- Repo-relative links for targets inside the repo; full `https://github.com/...` URL for external repos.
- Five conventional categories for a user-wide catalog: **Coding Conventions**, **Personal Tools**, **Opensource Tools**, **Research Notes**, **Design Specs**. Raise the bar for a sixth (≥3 entries with no natural home).

The saturation principle still applies — even a big catalog is trying to make the reader self-sufficient for discovery ("which of these should I reach for?"), not make them click through to find out.

The three shapes — leaf, hub, catalog — are a continuum, not categories. Pick the amount of absorption proportional to the fan-out: full coverage for 1, per-item digest for a handful, compressed catalog for many.

## Frontmatter and the SKILL.md symlink

Every `README.md` carries YAML frontmatter at the top:

```yaml
---
name: <directory-name>
description: <one-liner — what this thing does + when to use it>
---
```

- `name` matches the directory name.
- `description` is the string Claude's skill-matcher sees when deciding whether to surface this doc. Write it as both a capability ("what it does") and a trigger ("when to use it") separated by a period. Specific keywords beat vague framing.
- Every directory also gets a `SKILL.md` symlink pointing at `README.md` (`ln -s README.md SKILL.md`). This keeps any directory discoverable as a skill without having to decide up front which ones "count." `godzkilla` finds skills via `rglob("SKILL.md")`, which matches the symlink by name; reading the file follows the symlink.
- Uniform discipline — no conditional "is this a skill?" branch. If a directory is worth a canonical README, it's worth being discoverable by the skill-matcher too.

## Updating an existing README

When changes land under the README's directory, the README tends to drift. Update it incrementally rather than from scratch.

```bash
# Find the commit that last touched this README:
git log -1 --format=%H -- <path>/README.md

# Review changes under the directory since then:
git log <last-readme-commit>..HEAD -- <subpath>
git diff <last-readme-commit>..HEAD -- <subpath>
```

- Scope with the subpath — for `skills/foo/README.md`, use `skills/foo/` as the subpath.
- If the README is at repo root, drop the subpath filter (use all commits since).
- Read the diff, then update the README to reflect the changes. Orientation usually stays; per-sub-item digests and catalog entries are the parts that drift.
- For hub and catalog READMEs, also check whether any links point to files that were renamed or deleted (`git log --diff-filter=D --name-only <last>..HEAD -- <subpath>`). Broken pointers in a catalog are worse than no entry.
- If a new sub-thing landed under the directory, absorb it: add a `##` block with a digest + inline `-> [spec]` link. Don't just append a bare link.

Commit the README update alongside the work that caused it when possible — otherwise in a dedicated follow-on commit.

## Worked examples

**Converting a SKILL-only skill to the canonical shape**:

```bash
cd skills/foo
git mv SKILL.md README.md
ln -s README.md SKILL.md
# Keep the frontmatter. Check the README actually saturates normal use;
# if it's just a stub with "see X for details", absorb X's normal-use
# surface into the README.
git add README.md SKILL.md
git commit -m "skills/foo: README-ify SKILL.md; symlink SKILL.md"
```

**Starting a README from scratch**:

- Write frontmatter (`name: <dir>`, `description: <what> + <when>`), then `# <name>`, then a short orientation (1–3 lines).
- If the directory is a leaf, write body sections that cover the thing end-to-end.
- If the directory has sub-things, write a `##` block per sub-thing — concept, minimal usage, `-> [spec](path/)` pointer.
- If the fan-out is big enough that per-item digests stop fitting, switch to the `what:` / `when:` catalog format.
- Symlink `SKILL.md → README.md` in the same commit.
