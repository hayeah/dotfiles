---
name: readme
description: Write one canonical README.md per directory (symlinked as SKILL.md when the directory is also a skill). TLDR at the top, body in the middle, an optional index of links fanning out to deeper docs at the bottom. Use when creating a new README or updating one after code changes.
---

# readme

One canonical entry-point doc per directory: `README.md`. If the directory is also an agent skill, `SKILL.md` is a symlink to `README.md` — never a second real file. The reader should be able to use the thing by reading the top of the doc alone; everything deeper is linked out.

## TLDR

- File layout per directory:
  ```
  foo/
    README.md       # real file — frontmatter (if skill) + TLDR + body + (optional) index of links
    SKILL.md        # symlink → README.md (only when foo is a skill)
  ```
- Document skeleton, top to bottom:
  ```
  ---
  name: foo                # frontmatter, only when the dir is a skill
  description: one line, what + when
  ---

  # foo

  ## TLDR
  one paragraph + minimal usage example — the API surface a reader needs to use this

  ## <body sections...>
  deeper docs, architecture, reference, quirks

  ## <index of links>     # only if the dir fans out to sub-docs worth linking
  - [path/to/sub-doc.md](path/to/sub-doc.md) — one-line hook on why you'd read this
  ```
- Create the symlink in the same commit as the README:
  ```bash
  cd skills/foo
  ln -s README.md SKILL.md
  ```

## The TLDR section

- Explicitly labeled `## TLDR`. Not "the paragraph above the first `##` header." A labeled section is grep-able and unambiguous.
- Contents: one short paragraph stating what the thing is + one or two minimal, copy-pasteable usage examples. If install is a one-liner, it can fit inside TLDR; otherwise put it in a separate `## Install` section below.
- **A reader who only ever reads TLDR should be able to use the thing.** That's the bar. If that's impossible, the TLDR is wrong (or the thing is too broad — split it).
- Absence of TLDR means "this README hasn't been reshaped yet." It is **not** a deliberate "low importance" signal. Agents should read the whole doc when no TLDR is present, not skip the doc.
- When updating a README, the TLDR is the part most likely to stay stable. If the TLDR changes meaningfully, the thing's API surface or purpose changed — flag that in the commit message.

## Body

Everything a reader needs beyond TLDR: install, usage reference, architecture, quirks, known pitfalls. Structure with `##` section headers. No rules here beyond "write what the reader actually needs" — body shape varies by subject matter.

## Index of links

Below the body, optionally, list sub-docs / sub-guides / sub-libs / design specs / related files worth inducing on-demand reading of. One README per directory; an index-of-links section is how the canonical README fans out to everything else.

Each entry is a link + a one-line hook on why you'd read it:

```markdown
## Deeper reading

- [docs/design.md](docs/design.md) — Why the dispatch loop uses a ring buffer instead of a channel
- [docs/protocol.md](docs/protocol.md) — Wire-format spec for the agent-side tap API
```

Rules:

- The hook is a single short sentence. No period. No generic "about X" phrasing — state the actual reason to read.
- Link text uses the repo-relative path (show location at a glance).
- Heading name is whatever fits the content: `## Deeper reading`, `## Sub-guides`, `## Catalog`, `## Related`. Pick one, don't agonize.

### When the fan-out is a large catalog

If the index grows past ~5 entries and readers will discover by topic, richen the format: group under category headers and use `what:` / `when:` nested bullets per entry. The classic shape (live instance: `~/github.com/hayeah/dotfiles/INDEX.md`):

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

The fan-out format is a dial, not a switch: one-line + hook for small indexes, `what:`/`when:` for large catalogs, continuum in between. Same section in the same doc, same canonical shape — it just gets more structure as the linked surface grows.

## Frontmatter and the SKILL.md symlink

Skill directories need YAML frontmatter at the top of `README.md`:

```yaml
---
name: <skill-identifier>
description: <one-liner — what the skill does + when to use it>
---
```

- `name` matches the directory name.
- `description` is the string Claude's skill-matcher sees when deciding whether to load the skill. Write it as both a capability ("what it does") and a trigger ("when to use it") separated by a period. Specific keywords beat vague framing.
- Frontmatter lives in `README.md`. `SKILL.md` is a symlink (`ln -s README.md SKILL.md`) so that agent-side skill loaders that look for `SKILL.md` by name still find it. `godzkilla` discovers skills via `rglob("SKILL.md")`, which matches the symlink by name; reading the file follows the symlink.
- Non-skill directories just skip the frontmatter block.

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
- Read the diff, then update the README to reflect the changes. TLDR usually stays; body sections and index entries are the parts that drift.
- If there's a large-catalog index, also check whether any catalog entries point to files that were renamed or deleted (`git log --diff-filter=D --name-only <last>..HEAD -- <subpath>`). Broken links in a catalog are worse than no entry.

Commit the README update alongside the work that caused it when possible — otherwise in a dedicated follow-on commit.

## Worked examples

**Converting a SKILL-only skill to the canonical shape**:

```bash
cd skills/foo
git mv SKILL.md README.md
ln -s README.md SKILL.md
# If the README lacks ## TLDR, add one at the top. Keep the frontmatter.
git add README.md SKILL.md
git commit -m "skills/foo: README-ify SKILL.md; symlink SKILL.md"
```

**Starting a README from scratch**:

- Write frontmatter (if skill), then `# <name>`, then `## TLDR` with a paragraph and one usage block.
- Add body sections for anything a user needs beyond TLDR: `## Install`, `## Usage`, `## How it works`, `## Quirks`.
- If there are sub-docs worth linking, add a final index section with one-line-plus-hook entries.
- Symlink `SKILL.md → README.md` in the same commit if the directory is a skill.

**Examples already in this shape in `~/github.com/hayeah/dotfiles/skills/`**:

- [cloudflare-tunnel/](../cloudflare-tunnel/README.md) — body-heavy reference, no index section needed
- [tmuxcap/](../tmuxcap/README.md) — installation + usage + formats
- [plist/](../plist/README.md) — richer reference-style body
- [gobin/](../gobin/README.md) — TLDR-style quickstart up top

**Dogfood**: this skill's own README (the file you're reading) follows its own rules — labeled `## TLDR` at the top, one-line-plus-hook format for the worked-example links above, frontmatter with name + description, `SKILL.md` symlinked to this file.

## What this skill doesn't do

- Does not cover `$MDNOTES_ROOT/<date>/` ad-hoc notes — that's the [mdnote](../mdnote/SKILL.md) skill, different purpose.
- Does not retire or replace the legacy [readme-skill](../readme-skill/SKILL.md) / [indexmd](../indexmd/SKILL.md) skills; they coexist for now. When working on documentation tasks, prefer this skill.
