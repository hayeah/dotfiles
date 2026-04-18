---
name: indexmd
description: Create and maintain INDEX.md — a wiki-style awesome-list of pointers into the user's skills, libs, personal tools, opensource recipes, research notes, and design specs. Use when adding/removing entries from INDEX.md or considering whether something belongs in it.
---

# indexmd

INDEX.md lives at the root of `~/github.com/hayeah/dotfiles/INDEX.md`.
It is the **wiki entry point** — agents and humans land here to find
*where* documentation lives, not *what* it says.

Live file: [../../INDEX.md](../../INDEX.md)

## Purpose

- Pointers, not content. Each entry is one line: a link plus a short hook.
- Optimized for **discovery by topic**. If the user has had to re-explain
  "where is X documented" twice, X earns an INDEX entry.
- Complements `/mdnote` (dated, ad-hoc, throwaway). INDEX.md is the
  curated, durable layer.

## Non-goals

- Not a tutorial — no prose, no code blocks, no rationale.
- Not a replacement for `README.md` / `SKILL.md` / `libs/README.md`.
  Those say *what*; INDEX.md says *where*.
- Not a changelog. `git log` handles that.
- Not exhaustive. Skip anything an agent can find by grepping the repo
  (e.g. individual zsh init fragments, single-file configs).

## Format

**Flat list.** Every documented thing is its own top-level entry under
its category — no parent/child clustering. Each entry has a full-path
link and **two nested labelled bullets**:

```markdown
## <Category>

- [<full/path/to/doc>](<full/path/to/doc>)
  - what: <what it is and what it does, 20–30 words>
  - when: <when to reach for it, 20–30 words>
```

Concrete example:

```markdown
- [skills/browser/](skills/browser/SKILL.md)
  - what: Interactive browser automation via Chrome DevTools Protocol — persistent or one-shot sessions, screenshots, JS eval
  - when: The task requires a real visible browser (login, captcha, complex SPA) or the user wants to interact with the page directly
- [skills/browser/plugins/chatgpt/](skills/browser/plugins/chatgpt/)
  - what: ChatGPT plugin for the browser skill — capture conversations, threads, and shared chats from a logged-in chatgpt.com session
  - when: Scraping or archiving the user's chatgpt history, or driving an automated chatgpt session inside an outer agent loop
```

Rules:

- **Flat — no entry nesting.** A skill's sub-guides are siblings of the
  skill itself, not nested children. Same for libraries and their
  sub-modules. The only nested bullets are `what:` and `when:`.
- **Full path in the link text.** Show the full repo-relative path
  (e.g. `skills/browser/plugins/chatgpt/`), not an abbreviated leaf
  name. Lets the agent see the location at a glance.
- **`what`**: what the thing is and what it does. The "is" half
  identifies the kind (library, CLI, style guide, design doc); the
  "does" half names the capability.
- **`when`**: situations that should send the agent to this entry.
  Concrete decision triggers — specific tasks, questions, or signals.
  Avoid generic "when working with X"; prefer the actual moment of
  need. No need to start every line with "Use when…" — drop the
  preamble and lead with the trigger itself.
- **Target 20–30 words** per `what` and per `when`. Shorter is too
  sparse; longer means the hook is doing the linked doc's job.
- Repo-relative links for targets inside dotfiles; full
  `https://github.com/...` URL for external repos.
- Sentence-case. No trailing period on `what`/`when` lines.
- No numbered lists, no numbered headings.
- Category headers `##`. Sub-categories (rare) `###`. Never deeper.

### Ordering inside a category

Group related entries together (a SKILL.md and its sub-guides stay
adjacent in the flat list), but keep the structure flat — they are
still separate entries, not nested. Within a group, list the index
doc first, then its supporting docs.

## Categories

There are exactly five. **Be reluctant to add a sixth.** New
categories must clear a high bar: ≥3 entries with no natural home.

- **Coding Conventions** — language-agnostic libs (`libs/`) and
  language-specific style guides (`skills/golang/`, `skills/python/`,
  `skills/swiftui/` …).
- **Personal Tools** — things the user built themselves. Skills with
  a tool flavor live here, plus standalone repos under
  `~/github.com/hayeah/*`. Anything unlikely to appear in an LLM
  training set qualifies.
- **Opensource Tools** — distilled recipe collections for complex
  third-party tools (e.g. duckdb). Not a man-page rewrite — the kind
  of "known-good usage" the user keeps re-deriving otherwise.
- **Research Notes** — high-level mental models. "How does X actually
  work" for systems the user wants to keep handy (swiftui internals,
  wireguard protocol, etc.). Promoted from `$MDNOTES_ROOT` once durable.
- **Design Specs** — durable design docs for the user's own systems.
  Live in `docs/` inside dotfiles. Short-lived design chatter stays
  in `$MDNOTES_ROOT`.

## What NOT to include

- Inline content (examples, snippets, command listings) — put it in
  the linked doc, not INDEX.md.
- Fine-grained config (zsh init files, mise pins, individual aliases).
  README.md and the config files themselves cover those.
- Dated `$MDNOTES_ROOT/<date>/` notes that haven't earned promotion.
- Transient project state (in-flight branches, open PRs, ticket lists).

## Workflow

### Add an entry

- Decide the category. If the entry doesn't obviously fit one of the
  five, file it under the closest. Do not add a new category.
- Write the hook in the same voice as a skill `description`
  frontmatter: lowercase, no period, fewest words possible.
- If the target is a skill that fans out (≥2 sub-guides worth naming),
  nest sub-bullets under it.
- Insert in alphabetical order **within the cluster it belongs to**
  (e.g. all `skills/*` entries under Personal Tools stay grouped),
  unless logical grouping says otherwise.

### Remove an entry

- Remove the moment the target is deleted, renamed, or merged away.
  A broken link in INDEX.md is worse than no entry.

### Promote a research note

- Move the durable parts out of `$MDNOTES_ROOT/<date>/<title>.md` into
  `docs/research/<topic>.md` (create the directory if absent).
- Add a Research Notes entry pointing at the new location.

### Promote a design spec

- Move the spec from `$MDNOTES_ROOT/<date>/` into `docs/<title>.md`.
- Add a Design Specs entry pointing at the new location.

## Maintaining the SKILL.md

This skill (`skills/indexmd/SKILL.md`) and `INDEX.md` evolve together.
When the user asks for an INDEX.md improvement that changes the *rules*
(format, categories, what counts), update **both files** in the same
edit pass:

- Change the rule here in SKILL.md.
- Apply the rule to INDEX.md so the live file reflects current
  conventions.

When the user asks for an INDEX.md change that is purely an *entry*
add/remove/edit, only INDEX.md needs to change.
