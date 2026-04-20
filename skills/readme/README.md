---
name: readme
description: Write one canonical README.md per directory — always with SKILL-compat frontmatter and a SKILL.md symlink. Grade each covered item AAA / AA / A by importance: AAA is inlined in the body, AA is a digest with a pointer to a sub-doc, A is a pointer with a terse hook. README size budget forces the ranking; promote/demote as usage shifts. Same layering generalizes to changelogs, friction logs, and other accumulating wiki docs. Use when creating a new README or updating one after code changes.
---

# readme

One canonical entry-point doc per directory: `README.md`, always with SKILL-compat frontmatter (`name` + `description`) and always symlinked as `SKILL.md`. Every item it covers gets graded **AAA / AA / A** by importance: AAA is inlined in the body, AA is a `##` digest with a pointer to a sub-doc, A is just a pointer with an optional hook. The number of AAA items is bounded by how big you're willing to let the README grow, which forces a ranking.

- [TLDR](#tldr) — file layout, document skeleton, AA and A sketches at a glance
- [Three grades: AAA / AA / A](#three-grades-aaa--aa--a) — definitions, promote/demote signals, size budget
- [Frontmatter and the SKILL.md symlink](#frontmatter-and-the-skill-md-symlink) — the always-required header and symlink
- [Updating an existing README](#updating-an-existing-readme) — git-log-subpath incremental workflow
- [Worked examples](#worked-examples) — converting an existing doc, starting from scratch
- [The layering beyond READMEs](#the-layering-beyond-readmes) — same AAA/AA/A for changelogs, friction logs, other wiki docs

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

  <quick-link list of AAA items — lets the reader jump to the hot path>
  - [<AAA item 1>](#anchor-1) — one-line hook
  - [<AAA item 2>](#anchor-2) — one-line hook

  ## <first body section / AAA item>
  inlined content — the reader reads it here, no click

  ## <next body section or AA block>
  AA blocks end with `-> [spec](path/to/deeper-doc)` pointing at overflow
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

## Three grades: AAA / AA / A

Every item the README covers (a sub-thing, a concept, a section of body content) sits in exactly one grade. The grade dictates where the content lives and how much README space it takes.

**Fan-out** = the set of items the README organizes and points at: sub-directories, sub-modules, sub-docs, sub-skills, plus any in-body topics that could plausibly earn their own section. Every item in the fan-out gets a grade.

### AAA — inlined

Content lives fully in the README body. No link to follow; the reader reads it here. Expensive in README space, so reserved for the **hot path** — what readers hit on a normal task:

- Concept and orientation the reader needs to get started.
- Default behavior, common-case usage.
- The one gotcha that would otherwise get re-discovered via a stack trace.
- The install/setup one-liner.

AAA tends to dominate when the directory's contents are small or tightly coupled enough to cover end-to-end without distinguishing into separate items — the body is mostly inlined commentary rather than per-item digests or pointers.

**Quick-link list at the top.** Directly below the orientation paragraph, include a short bulleted list of the README's AAA items — one line per item, linking to its `##` anchor with a one-line hook. A mini-TOC of the hot path so the reader can jump straight to what they need instead of scanning:

```markdown
- [Install](#install) — one-liner via `uv tool install -e .`
- [Usage](#usage) — `foo -t <target>` for the common case
- [Formats](#formats) — supported output extensions
```

Only AAA items go in the quick-link list. AA blocks and A entries stay in the body; the list is for the hot path, not a full TOC.

### AA — absorbed (digest + pointer)

A `##` block that digests the item and points to a sub-doc for full detail. Format:

- A one- or two-paragraph description — concept + any quirks a normal user needs.
- A minimal copy-pasteable usage example (per language, if multi-language).
- A trailing `-> [spec](path/to/sub-doc/)` pointer (or several, pipe-separated) to the full reference.

Sketch:

```markdown
## logger — Structured Logging

Colored console output + JSONL file log. `LOG_LEVEL` (debug/info/warn/error,
default info) controls verbosity.

    from hayeah.core.logger import new
    log = new("my-tool")
    log.info("starting", port=8080)

-> [spec](path/to/logger/)
```

The reader can use the item from the digest alone; they descend to the spec only when they need the full API or design rationale. The `-> [spec](...)` target is often another README in this same shape — recursion — and the reader stops descending once their question is answered.

### A — overflow (pointer with optional hook)

Just a pointer, with a terse hook where useful. At scale (15+ items), compresses to the `what:` / `when:` catalog format:

```markdown
## <Category>

- [<full/path/to/doc>](<full/path/to/doc>)
  - what: <what it is and what it does — 20–30 words>
  - when: <situations that should send an agent here — 20–30 words>
```

- Flat list within a category. A skill and its sub-guides are siblings, not nested children. The only nested bullets are `what:` and `when:`.
- `what`: the "is" half identifies the kind (library, CLI, style guide, design doc); the "does" half names the capability.
- `when`: concrete decision triggers. Drop the generic "Use when…" preamble; lead with the actual moment of need.
- 20–30 words each — shorter is too sparse; longer means the hook is doing the linked doc's job.
- Sentence-case. No trailing period on `what`/`when` lines.
- Repo-relative links for targets inside the repo; full `https://github.com/...` URL for external repos.
- Five conventional categories for a user-wide catalog: **Coding Conventions**, **Personal Tools**, **Opensource Tools**, **Research Notes**, **Design Specs**. Raise the bar for a sixth (≥3 entries with no natural home).

An A entry still has to orient the reader ("which of these should I reach for?"). If the hook can't do that job, the item is graded too low — promote it to AA.

### Typical grade distributions

The README is commentary on what's in the directory — whatever that is, coherent or kitchen-sink. Coherence level doesn't change the grading discipline; it just changes the mix of grades the README ends up with:

- **Small or tightly-coupled contents** (one tool, one library module, a few closely-related files): mostly AAA — the README inlines most of the commentary end-to-end because there's little to distinguish into separate items. Any overflow (design notes, full reference) goes to sub-docs linked inline from the body as one-off A entries.
- **Several distinguishable items** (a handful of sub-things worth their own section): AAA for shared orientation + AA blocks per item. Classic hub shape.
- **Many loosely-related items** (wiki root, kitchen-sink collection): AAA for orientation + mostly A catalog entries grouped under categories, with a few AA blocks for the items hot enough to earn the bigger digest.

Any real README can mix all three. The grading is per-item; the shape emerges from the mix.

### Promoting and demoting

Items migrate between grades as usage patterns shift:

- **Promote A → AA**: the catalog hook isn't enough; readers have to click through for context that should have been in the preview. Expand the entry to a `##` block with a digest.
- **Promote AA → AAA**: the digest is the only thing anyone reads, or the same sub-doc detail keeps getting re-looked-up via the pointer. Inline the block and retire the sub-doc (or keep it as overflow for rare depth).
- **Demote AAA → AA**: a detail is blurring the body and most readers don't need it. Split it off into a sub-doc; leave a digest in the body.
- **Demote AA → A**: a `##` digest has grown into a mini-reference — it's doing the sub-doc's job. Trim to a catalog entry; let the sub-doc carry the weight.

**Default lean: grade up when unsure.** A slightly longer README costs less than the reader clicking through for a detail that should have been at hand. Over-offloading is more painful (and harder to notice) than over-inlining.

### The size budget

There's no hard limit — a per-README feel for "how long before scanning this gets annoying." Skill-level READMEs typically tolerate 200–400 lines; library hubs comfortably reach 600; wiki-root catalogs cap at whatever keeps the category lists scannable. When the budget tightens, items demote (AAA → AA → A); when it relaxes, items promote. The budget is the pressure that forces the ranking.

## The layering beyond READMEs

The same AAA/AA/A discipline applies to any accumulating doc where the reader's attention is limited. A **changelog**: recent releases inlined in full (AAA), older releases digested per version with a pointer to the detailed notes (AA), ancient history as a catalog of versions and dates (A). A **friction log**: hot open frictions inlined with full context (AAA), resolved-but-instructive ones digested (AA), archived/historical ones pointered (A). A **design-decision log**: load-bearing current decisions inlined, superseded ones digested, legacy pointered.

Same wiki-structure reasoning: front-load what matters now, digest the middle, link out to the long tail. Same budget pressure forces the ranking. The grading is generalizable; the README is just the most common home.

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
