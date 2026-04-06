---
name: create-role
description: Create a "role" skill — an index SKILL.md that bundles related skills, guides, and conventions into a coherent agent persona.
globs: []
---

# Create Role Skill

A **role skill** is a SKILL.md that acts as an index over a cluster of related skills, guides, and conventions. It gives the agent a coherent persona and working context for a domain (e.g. "SwiftUI developer", "data pipeline engineer").

## Structure

```
skills/<role-name>/
  SKILL.md          # index — TLDRs + links to full docs
  guides/           # full reference docs (local copies or fetched)
```

## SKILL.md Layout

The SKILL.md has this shape:

```markdown
---
name: <role-name>
description: <one-line — what domain this role covers>
globs:
  - <file patterns that should auto-trigger this skill>
---

# <Role Title>

## <Topic A>

**TLDR**: <2-5 lines — enough for basic usage without reading the full doc>

<code example or key commands>

Key rules:
- ...
- ...

Full reference: [Topic A Guide](guides/topic-a.md)

## <Topic B>

**TLDR**: ...

Full reference: [Topic B Guide](guides/topic-b.md)
```

### Principles

- **TLDR first** — each section should be self-contained enough for basic usage. The agent only digs into the full guide when it needs details.
- **One role, one domain** — don't mix unrelated concerns. A "SwiftUI" role covers SwiftUI patterns, Xcode tooling, and the app's state architecture — not also "how to deploy to TestFlight".
- **Link, don't inline** — keep the SKILL.md scannable. Long docs go in `guides/`.
- **Concrete over abstract** — show the commands, the file layout, the code pattern. Skip philosophy.

## Guides Directory

Full reference docs live in `guides/`. Sources can be:

- **Local markdown** you write directly
- **Fetched from a URL** — download and save a local copy so the agent doesn't need network access at read time

```bash
# Fetch a remote doc into guides/
curl -sL https://raw.githubusercontent.com/user/repo/master/docs/some-guide.md \
  -o skills/<role-name>/guides/some-guide.md
```

When a guide comes from an external repo, add a `source` field in the YAML frontmatter so it can be programmatically refreshed:

```markdown
---
source: https://raw.githubusercontent.com/user/repo/master/docs/some-guide.md
---

# Some Guide
...
```

## Example: `skills/webui`

The `webui` role bundles Vite+ toolchain, MobX state, browser testing, and tap API into one skill. Directory layout:

```
skills/webui/
  SKILL.md
  guides/
    webui-template.md      # project template reference
    viteplus.md            # Vite+ tooling guide
    libraries.md           # library choices
    mobx-global-state.md   # state management pattern
    web-tap-api.md         # agent-driven UI testing API
    index.css              # design token reference
```

The SKILL.md is an index with TLDR sections for each concern:

- **Dev Workflow** — how to start the server, open a browser session, screenshot states
- **File Conventions** — PascalCase components, page-grouped layout
- **New Project** — template clone commands + key setup steps
- **Browser Testing** — screenshot, eval, one-shot vs persistent sessions
- **MobX Global State** — one tree, direct set, `__DOC__`, key rules
- **Web Page Tap API** — `window.__tap__` convention, `$` prefix for DOM refs

Each section follows the pattern:

```markdown
## MobX Global State

**TLDR**: One MobX observable tree rooted in a single `AppStore`,
with child stores organized by domain. All components observe
paths in the tree via `observer()`.

<code example>

Key rules:
- **One tree** — AppStore -> child stores -> plain data
- **Direct set** for single-property writes, **action methods** for multi-property
- ...

Full reference: [MobX Global State Guide](guides/mobx-global-state.md)
```

The agent reads the SKILL.md for quick context. It only opens a guide when it needs the full details (e.g. all MobX patterns, or the complete template README).

## Workflow

- Identify the cluster of related skills/docs/conventions
- Create the directory: `skills/<role-name>/`
- Gather guides into `guides/` — fetch remote docs, copy local notes
- Write the SKILL.md index with TLDR sections linking to each guide
- Register with godzkilla if needed: `godzkilla sync`
