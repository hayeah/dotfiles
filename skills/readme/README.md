---
name: readme
description: Write one canonical README.md per directory — always with SKILL-compat frontmatter (name + description) and always symlinked as SKILL.md. The README saturates normal-use needs for the directory and everything in it; sub-docs are read on demand, only when the reader needs more detail than the README provides. Use when creating a new README or updating one after code changes.
---

# readme

One canonical entry-point doc per directory: `README.md`. `SKILL.md` is always a symlink to `README.md` — never a second real file. Every README carries YAML frontmatter (`name` + `description`) at the top — the SKILL-compat header — so any directory is discoverable as a skill without a separate decision about which ones "count."

**The README absorbs enough that readers do normal tasks from the README alone.** Sub-docs are the overflow layer — full API reference, edge cases, design rationale, rarely-needed depth. Where to draw the line between "normal" and "overflow" is a balance judgment, not a rule: inline too much and the README grows long and blurry (the reader skims past corner-case sections to find the one usage block they need); offload too much and the README under-covers (the reader has to click out for what should be a README-level task).

**The structure is recursive.** An overflow pointer like `-> [spec](path/)` can target a plain file OR another directory that carries its own README in this same shape — orientation, absorbed body sections, its own fan-out pointers. A reader descends only as far as their question needs; each level is self-sufficient for the things it digests.

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
- When the fan-out is too big for per-item digests, the body (or a
  section of it) compresses to a catalog — one line per entry, with
  labelled `what:` / `when:` hooks:
  ```
  ## <Category>

  - [path/to/thing/](path/to/thing/)
    - what: <what it is and what it does — 20–30 words>
    - when: <what should send an agent here — 20–30 words>

  - [path/to/other-thing/](path/to/other-thing/)
    - what: ...
    - when: ...
  ```
- Create the symlink in the same commit as the README:
  ```bash
  cd <dir>
  ln -s README.md SKILL.md
  ```

## Absorb vs. offload — the balance

Every README has overflow material it could either inline (more coverage, longer and blurrier doc) or push to a sub-doc (crisper README, more clicking). The discipline is about finding the right line per section:

- **Default lean: when unsure, absorb.** A slightly longer README costs less than the reader clicking out for a common-usage detail. Over-offloading is more painful than over-inlining.
- **Offload** material that the reader reaches for occasionally, not per task: full API reference, design rationale, migration history, unusual edge cases, deep internals.
- **Absorb** material the reader hits on a normal path: concept, minimal usage, common quirks, defaults, the one gotcha that otherwise gets re-discovered via a stack trace.
- If you catch yourself writing "see X for details" as the only coverage of a sub-thing, the README is under-absorbing. Pull the normal-use surface into the body; keep `-> [spec](X)` as the pointer for the overflow.
- Every `-> [spec](X)` pointer can target either a plain file OR a directory that's itself a README in this shape. In the recursive case, the next level absorbs what's normal-use at *that* level and its own pointers fan out further. Readers stop descending once their question is answered.

**Fan-out** = the set of sub-things this README has to organize and point at: sub-directories, sub-modules, sub-docs, sub-skills — anything that earns its own `##` block or catalog entry. A README with no sub-things has a fan-out of zero; a README cataloging 50 skills has a big fan-out. The body-organization shapes below are three points along a continuum of fan-out size — not three distinct formats. Any real README can mix them within a single doc.

### Body organized around one thing

When the directory documents a single concept (one tool, one skill, one library module), the body is organized around that concept: orientation, usage, reference the normal user needs. Overflow — design doc, full API reference, internal spec, unusual edge cases — goes to sub-docs under `docs/` or similar, linked inline from the body section where their context lives.

### Body as per-sub-item digests

When the directory fans out to multiple sub-things, each gets its own `##` section containing:

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

The `-> [spec](...)` target is often a directory with its own README carrying further absorbed content and its own pointers — the recursion. The reader can use the sub-thing at this level alone; they only descend to the spec when they need the full API or design rationale, and from there can descend further if the spec itself fans out.

### Body as compressed catalog

When the fan-out grows past what you can digest in full — say 15+ sub-things spread across categories — compress each entry to a link plus a terse pair of labelled hooks:

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

Even at this density, the absorb-vs-offload balance still applies — a catalog hook is trying to make the reader self-sufficient for *discovery* ("which of these should I reach for?"), not make them click through to find out. If a `what:`/`when:` pair can't do that job, the entry is under-absorbing.

Each catalog target is typically a directory with its own README — follow a link and you're at the top of another level of this same recursive structure.

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
