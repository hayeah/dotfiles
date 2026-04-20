---
name: readme
description: Write one canonical README.md per directory (symlinked as SKILL.md when the directory is also a skill) — TLDR at top, index of links below. Use when creating a new README, updating one after code changes, or curating a repo-root catalog that fans out to many sub-docs.
---

# readme

One canonical entry-point doc per directory: `README.md`. If the directory is also an agent skill, `SKILL.md` is a symlink to `README.md` — never a second real file. The reader should be able to use the thing by reading the top of the doc alone; everything deeper is linked out.

## TLDR

- File layout per directory:
  ```
  foo/
    README.md       # real file — frontmatter (if skill) + TLDR + body + index of links
    SKILL.md        # symlink → README.md (only when foo is a skill)
  ```
- Document structure, top to bottom:
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

  ## <index of links>     # if the dir fans out to sub-docs / sub-libs / sub-skills
  - [path/to/sub-doc.md](path/to/sub-doc.md) — one-line hook on why you'd read this
  ```
- Two patterns: **Plain** (most directories) and **Wiki** (repo roots that catalog many things). Same skeleton, different index format.
- Create the symlink in the same commit as the README:
  ```bash
  cd skills/foo
  ln -s README.md SKILL.md
  ```

## Patterns

### Plain README

For any directory: a skill, a library module, a tool, a repo that does one thing. The index-of-links section (if any) points at sub-guides, design specs, or related files; each link gets one-line + hook.

Examples already in this shape in `~/github.com/hayeah/dotfiles/skills/`:

- [cloudflare-tunnel/](../cloudflare-tunnel/README.md) — body-heavy, no sub-docs, no index section needed
- [tmuxcap/](../tmuxcap/README.md) — installation + usage + formats
- [plist/](../plist/README.md) — richer reference-style body
- [gobin/](../gobin/README.md) — TLDR-style quickstart up top

### Wiki README

For a repo root (or any directory) that catalogs many documented things — per-language style guides, personal tools, design specs, third-party recipes. Same skeleton, but the index-of-links section is the bulk of the doc and uses a richer format.

Example: `~/github.com/hayeah/dotfiles/INDEX.md` is a Wiki-style catalog today. The same discipline applies whether it's named `INDEX.md` or lives under a `## Catalog` section inside a `README.md`.

Wiki-pattern index rules — keep these even as they migrate between files:

- Five fixed categories (raise the bar for a sixth): **Coding Conventions**, **Personal Tools**, **Opensource Tools**, **Research Notes**, **Design Specs**.
- Flat list — a skill and its sub-guides are siblings, not nested children. The only nested bullets are `what:` and `when:`.
- Each entry:
  ```markdown
  - [<full/path/to/doc>](<full/path/to/doc>)
    - what: <what it is and what it does — 20–30 words>
    - when: <situations that should send an agent to this entry — 20–30 words>
  ```
- Full repo-relative path in the link text (show the location at a glance).
- `what`: the "is" half identifies the kind (library, CLI, style guide, design doc); the "does" half names the capability.
- `when`: concrete decision triggers. Drop the generic "Use when…" preamble; lead with the actual moment of need.
- Sentence-case. No trailing period on `what`/`when` lines.
- Repo-relative links inside the repo; full `https://github.com/...` URL for external repos.

## The TLDR section

- Explicitly labeled `## TLDR`. Not "the paragraph above the first `##` header." A labeled section is grep-able and unambiguous.
- Contents: one short paragraph stating what the thing is + one or two minimal, copy-pasteable usage examples. If install is a one-liner, it can fit inside TLDR; otherwise put it in a separate `## Install` section below.
- **A reader who only ever reads TLDR should be able to use the thing.** That's the bar. If that's impossible, the TLDR is wrong (or the thing is too broad — split it).
- Absence of TLDR means "this README hasn't been reshaped yet." It is **not** a deliberate "low importance" signal. Agents should read the whole doc when no TLDR is present, not skip the doc.
- When updating a README, the TLDR is the part most likely to stay stable. If the TLDR changes meaningfully, the thing's API surface or purpose changed — flag it in the commit message.

## Index of links

For any README whose directory fans out to sub-docs or sub-libs worth linking.

**Plain pattern** — one line + hook per entry:

```markdown
## Deeper reading

- [docs/design.md](docs/design.md) — Why the dispatch loop uses a ring buffer instead of a channel
- [docs/protocol.md](docs/protocol.md) — Wire-format spec for the agent-side tap API
```

The hook is the "why you'd read this" induced read — a single short sentence, no period, no generic "about X" phrasing.

**Wiki pattern** — the `what:` / `when:` nested format under category headers. See [Wiki README](#wiki-readme) above.

**Rule of thumb**: if the README lists more than ~5 sub-docs and readers care about discovering by topic, use Wiki. Otherwise Plain. You can mix — a Plain README can still have a Wiki-style section near the bottom if one sub-area genuinely fans out.

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
- For a Wiki README, also check whether any catalog entries point to files that were renamed or deleted (`git log --diff-filter=D --name-only <last>..HEAD -- <subpath>`). Broken links in a catalog are worse than no entry.

Commit the README update alongside the work that caused it when possible — otherwise in a dedicated follow-on commit.

## Worked examples

**Converting a SKILL-only skill to the target shape**:

```bash
cd skills/foo
git mv SKILL.md README.md
ln -s README.md SKILL.md
# If the README lacks ## TLDR, add one at the top. Keep the frontmatter.
git add README.md SKILL.md
git commit -m "skills/foo: README-ify SKILL.md; symlink SKILL.md"
```

**Starting a Plain README from scratch**:

- Write frontmatter (if skill), then `# <name>`, then `## TLDR` with a paragraph and one usage block.
- Add body sections for anything a user needs beyond TLDR: `## Install`, `## Usage`, `## How it works`, `## Quirks`.
- If there are sub-docs worth linking, add a final `## Deeper reading` section with one-line-plus-hook entries.
- Symlink `SKILL.md → README.md` in the same commit if the directory is a skill.

**Dogfood**: this skill's own README (the file you're reading) follows its own rules — labeled `## TLDR` at the top, one-line-plus-hook format for internal links in the worked-examples list, frontmatter with name + description, `SKILL.md` symlinked to this file.

## What this skill doesn't do

- Does not cover `$MDNOTES_ROOT/<date>/` ad-hoc notes — that's the [mdnote](../mdnote/SKILL.md) skill, different purpose.
- Does not auto-update READMEs — the update workflow above is a prompt-driven manual pass. A `/update-readme` slash command could wrap it; not provided here.
- Does not retire or replace the legacy [readme-skill](../readme-skill/SKILL.md) / [indexmd](../indexmd/SKILL.md) skills; they coexist for now. When working on documentation tasks, prefer this skill.
