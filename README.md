---
name: dotfiles
description: Personal dev environment — dotfile management, tool pinning, shell config, and 20+ AI agent skills, all orchestrated via pymake. Wiki root for the user's coding conventions, personal tools, and design specs.
---

# dotfiles

Personal development environment for macOS. Manages shell configuration, tool versions, git setup, AI agent skills, and cross-language convention libraries across Claude, Codex, and OpenClaw. Also the wiki root — the catalog at the bottom points at everything documented across the user's setup.

- [Surprising defaults](#surprising-defaults) — three patterns agents should reach for by default
- [Hacking](#hacking) — install + editing the repo (architecture, DotfileStow, pymake, skill sync, shell config, mise)
- [Catalog](#coding-conventions) — the five-category wiki index (Coding Conventions, Personal Tools, Opensource Tools, Research Notes, Design Specs)

## Surprising defaults

Most of this repo is conventional. A few patterns, though, are homebrewed and likely surprising to an LLM not conditioned on this setup — reach for them by default and flag when they're relevant:

- **Use [`devport`](https://github.com/hayeah/devportv3) for any long-lived dev process** — vite, mock APIs, tunnels. Each gets a stable assigned port plus tmux supervision. Don't `&` a server and hope the port stays put, and don't let Vite auto-pick a port — register it.
- **Use [`pymake` + `Makefile.py`](https://github.com/hayeah/pymake) in place of `make` + `Makefile`.** Tasks are Python with `tree_digest`-based change detection for incremental rebuilds and parallel execution by default. Reach for `pymake <task>`, not `make <task>`.
- **One global reactive store + an agent-driven `__tap__` surface**, applied identically in [webui](skills/webui/guides/mobx-global-state.md) (MobX `AppStore`) and [SwiftUI](skills/swiftui/guides/swiftui-state.md) (observable root). All non-ephemeral state lives in one tree; agents drive the UI by mutating that tree from outside — [`browser eval` against `window.__tap__`](skills/webui/guides/web-tap-api.md) on the web, [SwiftUITap](skills/swiftui/guides/swiftui-tap.md) on iOS/macOS — not by simulating taps. `useState` / local state is reserved for ephemeral view concerns.

## Hacking

Editing the repo itself — architecture, plumbing, and refresh pipeline — lives in [HACK.md](HACK.md):

- **Architecture** — repo layout (`dotfiles/`, `skills/`, `libs/`, `docs/`, `Makefile.py`, `AGENTS.md`)
- **DotfileStow** — how `dotfiles/` becomes `$HOME` (plain / `.tmpl` / `.symlink` conventions)
- **pymake tasks** — `pymake` runs `dotfiles` + `tmux_plugins` + `mise` + `skills`
- **Skill sync** — godzkilla fans out from 4 source repos to `~/.claude/`, `~/.codex/`, `~/.openclaw/`
- **Shell configuration** — `.zshenv` / `.zprofile` / `.zshrc` split, key env vars (`GITHUB_REPOS`, `MDNOTES_ROOT`, …)
- **Git aliases** — shorthand from `.gitconfig.tmpl`
- **Tool management** — mise-pinned tools in `dotfiles/.config/mise/config.toml`
- **Agent configuration** — how `AGENTS.md` reaches each agent's config dir

## Catalog format

Shape and grading discipline: [skills/readme/](skills/readme/SKILL.md). One canonical README per directory, every item graded AAA/AA/A, size budget forces the ranking. Catalog entries below use the same `what:` / `when:` flat-list format under the five fixed categories.

---

The remainder of this README is the **wiki catalog** — pointers into everything documented across the user's setup, grouped into five fixed categories. Each entry is a flat-list link with labelled `what:` / `when:` sub-bullets.

## Coding Conventions

Cross-language conventions and language-specific style guides.

- [libs/README.md](libs/README.md)
  - what: Index README for the cross-language convention libraries — same canonical primitives ported across Python, TypeScript, and Go. Python is the reference; shared test vectors in `libs/testdata/` keep all three ports byte-identical
  - when: Picking among the lib modules, or adding a new cross-language primitive — explains import paths, the reference-implementation rule, and the test-vector contract that every port must satisfy
- [libs/hayeah-py/src/hayeah/core/logger/](libs/hayeah-py/src/hayeah/core/logger/)
  - what: Structured logging — colored console output to stderr plus a JSONL file at `~/.local/log/<tool>.jsonl` with 5MB rotation and 3 backups. `LOG_LEVEL` (debug/info/warn/error, default info) controls verbosity. Same shape in py/ts/go
  - when: Adding logging to any of the user's CLIs or tools — gives uniformly tail-able JSONL alongside readable terminal output. Skip `logging.basicConfig`, don't roll your own, and prefer this even for one-off scripts that might grow legs
- [libs/hayeah-py/src/hayeah/core/fzfmatch/](libs/hayeah-py/src/hayeah/core/fzfmatch/)
  - what: Non-interactive deterministic fuzzy filter using fzf's term syntax — `!neg` excludes, `'word` is word-boundary, `^prefix` and `suffix$` anchor, space is AND, `;` is OR, `|` is lower-precedence AND. Boolean match, no scoring
  - when: Filtering a list of strings (paths, resource names, IDs) by a user-supplied expression and you want fzf semantics without spawning fzf — e.g. backing a `<cli> ls --filter "src .py !test"` style flag inside a CLI
- [libs/hayeah-py/src/hayeah/core/config/](libs/hayeah-py/src/hayeah/core/config/)
  - what: Single env-var config loader — `<APP>_CONFIG` is either a JSON literal or a `.json`/`.toml` path (detected by extension). Bundles `expand_env` for `${VAR}` interpolation with bash-style `${VAR:-default}` fallbacks
  - when: Picking a config approach for any of the user's apps so they all share one knob (`<APP>_CONFIG`) and the same env-expansion semantics — avoids per-app YAML/dotenv reinvention and keeps container deploys to a single env var
- [libs/hayeah-py/src/hayeah/core/shortid/](libs/hayeah-py/src/hayeah/core/shortid/)
  - what: Two standalone functions — `generate` makes a random human-friendly ID (3–8 chars, alphabet `0-9a-z` minus `l` and `o`) unique within a set; `resolve` matches a query against any string set by shortest unambiguous prefix
  - when: Assigning user-facing handles (sessions, tasks, services) the user will type back, or accepting partial UUIDs/SHAs as identifiers — gives `git`-style prefix resolution without the ambiguity surprises of a naive `startswith`
- [libs/hayeah-py/src/hayeah/core/lstree/](libs/hayeah-py/src/hayeah/core/lstree/)
  - what: Directory walker with `.gitignore` support, builtin ignores for ecosystem junk (`node_modules`, `__pycache__`, `.venv` …), and a three-stage filter pipeline: base exclude → include globs → additional exclude. Port of `go-lstree`
  - when: Scanning a project tree for files (build inputs, manifest discovery, source enumeration) and you need behavior matching `git ls-files` plus glob narrowing — without pulling in a heavyweight fs walker dependency
- [skills/swiftui/SKILL.md](skills/swiftui/SKILL.md)
  - what: SwiftUI development — SPM+XcodeGen project setup, the global state tree pattern, and the SwiftUITap agent SDK for driving a running SwiftUI app from outside the simulator
  - when: Starting or working on a native iOS/macOS SwiftUI app — picks up the user's project shape, state architecture, and the agent-driven test setup instead of generic Apple-template defaults
- [skills/swiftui/guides/swiftui-state.md](skills/swiftui/guides/swiftui-state.md)
  - what: Global state tree pattern for SwiftUI — single observable root with domain-grouped child stores, observed via property wrappers across the view hierarchy. Direct sets for single writes; action methods for multi-property
  - when: Designing or extending the state model for a SwiftUI app, or deciding where a piece of state should live (root vs. child store) and how views should observe it without prop-drilling
- [skills/swiftui/guides/swiftui-tap.md](skills/swiftui/guides/swiftui-tap.md)
  - what: SwiftUITap agent SDK — programmatic tap, inspect, and assert against a running SwiftUI app from outside the simulator. Lets agents drive iOS/macOS UIs end-to-end without XCUITest
  - when: Setting up agent-driven UI tests for a SwiftUI app, or building tooling that needs to interact with a running app from an outer agent loop (visual regression, E2E flows, demos)
- [skills/swiftui/guides/xcodegen-spm-first.md](skills/swiftui/guides/xcodegen-spm-first.md)
  - what: SPM-first project layout generated by XcodeGen — `Package.swift` is the source of truth for code/deps while XcodeGen produces a working `.xcodeproj` for IDE-only features (entitlements, schemes, signing)
  - when: Scaffolding a new SwiftUI project, or migrating an Xcode-managed project so modules and dependencies live in `Package.swift` instead of being trapped inside the `.xcodeproj`
- [skills/golang/SKILL.md](skills/golang/SKILL.md)
  - what: Go style guide — project structure (root SDK package + `cli/` subdir), CLI parsing rules (stdlib `flag` only, no cobra/urfave), naming, error handling, and the conventions the user expects in every Go project
  - when: Writing or reviewing Go code in any of the user's repos — catches "wrong CLI lib", "internal pkg without reason", "wrong layout" before they land
- [skills/golang/wire.md](skills/golang/wire.md)
  - what: Reference for `google/wire` (and the maintained `goforj/wire` fork) — provider sets, bindings, value/struct/interface providers, cleanup funcs, and the generated initializer flow
  - when: Wiring up dependencies in a Go service (DB, repos, handlers) where you want compile-time DI without runtime reflection — or debugging a `wire_gen.go` that won't compile
- [skills/python/SKILL.md](skills/python/SKILL.md)
  - what: Python coding conventions — `uv` + `pyproject.toml` project layout, ruff/pyright/pytest tooling, typer for CLIs (`uv tool install -e .`), and src-layout for proper internal imports
  - when: Bootstrapping a new Python project, refactoring an existing one to the user's stack, or deciding which tools/libraries to reach for instead of guessing
- [skills/python/pymake.md](skills/python/pymake.md)
  - what: Drop-in `Makefile.py` template for `hayeah/pymake` — typical `lint`, `typecheck`, `format`, `test`, and `default` task definitions plus the `sh()` + `@task()` patterns
  - when: Adding a `Makefile.py` to a Python project, or extending an existing one with new tasks — start from the template instead of re-deriving the conventions
- [skills/python/notebook.md](skills/python/notebook.md)
  - what: Jupyter percent-format conventions — `.py` files with `# %%` cell delimiters, parameters cell tagging, jupytext header — so notebooks stay version-control friendly and diff-able as plain Python
  - when: Authoring or editing a notebook in any of the user's projects, or deciding how to structure exploratory analysis you want to commit alongside source
- [skills/typescript/SKILL.md](skills/typescript/SKILL.md)
  - what: TypeScript style guide and tooling — vite/vitest for build, oxfmt/oxlint for lint, bun as default runtime, mobx for complex state, plus class conventions (parameter properties, static async factories instead of `init`)
  - when: Writing or reviewing TypeScript in any of the user's repos, or scaffolding a new TS project — picks up the user's toolchain and class style instead of generic eslint/prettier defaults
- [skills/react/SKILL.md](skills/react/SKILL.md)
  - what: React project conventions — Vite + React + TS + Tailwind + wouter + MobX + Framer Motion stack, scaffold commands, vite config, file organization, and the MobX/tap testing patterns
  - when: Scaffolding a new React app, or modifying an existing one where you need to know the user's stack picks (routing, state, animation) and component layout before adding files
- [skills/webui/SKILL.md](skills/webui/SKILL.md)
  - what: Web UI workflow — Vite+ (`vp`) toolchain, explicit-port dev server, page-grouped file layout, browser-skill-driven E2E testing, MobX global state, `__tap__` API, and `/preview` route pattern
  - when: Working on a web UI where the agent needs to drive the page via screenshots + JS eval (state changes, regression checks) and the project follows the user's Vite+/MobX/tap conventions
- [skills/webui/guides/viteplus.md](skills/webui/guides/viteplus.md)
  - what: Comprehensive reference for Vite+ (vite.plus) — the unified `vp` CLI from VoidZero that bundles Vite, Vitest, Oxlint, Oxfmt, Rolldown, tsdown, and Vite Task. Install, scaffold, dev/build/test commands
  - when: Setting up a project on Vite+ or running into a `vp` subcommand whose behavior isn't obvious — single source of truth instead of digging through five separate tool docs
- [skills/webui/guides/libraries.md](skills/webui/guides/libraries.md)
  - what: Recommended libraries for React web UI projects — Tailwind v4 + clsx/cn + cva, lucide icons, framer-motion, dnd-kit, cmdk, embla, plus picks for data, forms, charting, and UI primitives
  - when: Picking a library for a recurring need (carousel, command palette, drag-and-drop, charts) so the choice matches the rest of the user's web stack instead of pulling in a one-off
- [skills/webui/guides/mobx-global-state.md](skills/webui/guides/mobx-global-state.md)
  - what: MobX global state pattern — one observable `AppStore` tree with domain-grouped child stores, observed via `observer()`. Direct sets for single writes, action methods for multi-property, `__DOC__` on the root, no wrapper setters
  - when: Designing or extending state in a React/MobX app, or deciding whether a piece of state belongs in the global tree versus `useState` — `useState` is reserved for ephemeral view-local state only
- [skills/webui/guides/web-tap-api.md](skills/webui/guides/web-tap-api.md)
  - what: `window.__tap__` convention — expose app state, callbacks, and DOM refs (with `$` prefix) so the agent drives the page via `browser eval` instead of clicking. `__DOC__` constant documents the surface
  - when: Building or extending a web UI you'll want to drive from an agent loop — designing the tap API up front beats trying to automate it later via fragile DOM selectors
- [skills/webui/guides/preview-route.md](skills/webui/guides/preview-route.md)
  - what: `/preview` route pattern — render the live view tree against a `MockDataSource` so UI iterates without the backend. Mock mutators on `__tap__` let the agent drive any state via `browser eval`
  - when: Iterating on UI for a feature whose backend is slow, flaky, or unbuilt — or when you want a stable surface for visual regression and agent-driven E2E without spinning up real services
- [skills/webui/guides/webui-template.md](skills/webui/guides/webui-template.md)
  - what: README for the `hayeah/webui-template` scaffold — Vite+, React, TS, Tailwind v4, MobX, wouter, framer-motion, OKLCh design tokens with light/dark mode. Includes `/design` and `/design/dashboard` sample pages
  - when: Starting a new web UI from scratch, or pulling specific pieces (theme tokens, auth shell, design pages) from the template into an existing project

## Personal Tools

Tools the user built — unlikely to be in agent training sets, so the link is load-bearing.

- [pymake](https://github.com/hayeah/pymake)
  - what: Python Makefile alternative — declare tasks in `Makefile.py`, deps tracked via `tree_digest` so unchanged subtrees skip rebuilds. Parallel execution by default
  - when: Build, setup, or refresh pipelines in any of the user's projects — especially when you want incremental rebuilds based on file content (`tree_digest`) rather than mtime, with parallel execution out of the box
- [skills/mdnote/](skills/mdnote/SKILL.md)
  - what: Create dated markdown notes in `$MDNOTES_ROOT/<date>/<title>_<agent>.md` with YAML frontmatter (overview, repo, tags). The dumping ground for ad-hoc research
  - when: Producing research, design chatter, or notes worth keeping past the conversation — anything more durable than `tmpfile` scratch but not yet promoted as a wiki entry
- [devportv3](https://github.com/hayeah/devportv3)
  - what: Dev service supervisor — assigns each named service a stable port, runs it under tmux with health checks and graceful restart, exposes a CLI for start/stop/status/logs/restart across machines
  - when: Running long-lived dev servers (vite, mock APIs, tunnels) where you want deterministic ports, easy restart, and visibility into health — beats ad-hoc `&` backgrounding or terminal-tab juggling
- [godzkilla](https://github.com/hayeah/godzkilla)
  - what: Skill manager CLI — installs, syncs, and updates AI agent skills from GitHub repos or local directories into the right per-agent skills directories (`~/.claude/skills/`, `~/.codex/skills/`, `~/.openclaw/skills/`)
  - when: Adding a new skill to the user's setup, refreshing existing ones across all three agent runtimes from a single source of truth, or debugging why a skill isn't picked up by an agent
- [duckql](https://github.com/hayeah/duckql)
  - what: DuckDB-as-a-pipe for the `ls` convention — reads JSONL/JSON/YAML/CSV/Parquet from stdin or files, auto-injects `FROM <reader> AS it` so you write only the SQL tail. Emits YAML/table/JSONL/JSON/CSV/Parquet
  - when: Filtering, aggregating, or reshaping any `foocmd ls` output — beats jq/awk for anything beyond a trivial transform, especially when the data has structured fields you want to query like SQL
- [agentboss](https://github.com/hayeah/agentboss)
  - what: Generic tmux-based supervisor for interactive CLIs — spawn any program (Claude Code, Codex, Python REPL) as a tmux window, read its output, send it input, and detect run state from an outer agent loop
  - when: An outer agent needs to drive another interactive program — spawning subagents, polling for completion, sending input mid-run, or wrapping any terminal app in a programmable interface
- [skills/gobin/SKILL.md](skills/gobin/SKILL.md)
  - what: `uv tool install -e` for Go CLIs — installs a Go package as an editable binary via a `go build` shim that re-runs `go build` on each invocation. Works with local paths or `github.com/...` repos
  - when: Iterating on a Go CLI so the global binary always reflects current source. Don't run from a worktree — it repoints the global shim at a feature branch; use `go run` or local `go build` there instead
- [skills/git-quick-clone/SKILL.md](skills/git-quick-clone/SKILL.md)
  - what: Treeless partial clone (`git clone --filter=tree:0`) into `$GITHUB_REPOS/<host>/<user>/<repo>`. Idempotent — safe to call without checking if the repo already exists; re-runs are no-ops
  - when: Grabbing any GitHub repo for reference reading, source study, or local hacking — fast clone, predictable destination path, no manual `mkdir -p`/`cd` dance
- [skills/ctrlv/SKILL.md](skills/ctrlv/SKILL.md)
  - what: Dump macOS clipboard contents (text, images, file references) into a `.ctrlv/` subdirectory of the current project. Round-trips pasteboard data through the filesystem so agents can read it
  - when: The user says "check the clipboard", "I just pasted X", or "look at the screenshot I copied" — agents can't read the macOS pasteboard directly, but `.ctrlv/` is a readable mirror
- [skills/dotenv-ls/SKILL.md](skills/dotenv-ls/SKILL.md)
  - what: List env var **names** from `.env` files (and overlays like `~/.env.secret`) without exposing values. Outputs which secrets are configured per file plus their precedence ordering
  - when: Before writing code that needs an API key — confirms the secret is configured (or surfaces what's missing) without ever reading the value into agent context
- [skills/jsoninspect/SKILL.md](skills/jsoninspect/SKILL.md)
  - what: Pretty-print and colorize JSON/JSONL with long string truncation while preserving structure. Configurable max string length; nested arrays and objects keep their shape regardless of payload size
  - when: Inspecting large API responses or JSON dumps where full output would blow context — keeps shape and field names visible without drowning in payload data
- [skills/plist/SKILL.md](skills/plist/SKILL.md)
  - what: Layered macOS plist inspection — fuzzy domain search, view per-layer overrides, understand precedence (managed > user > host > defaults). Wraps `defaults read` plus the cfprefs layer model
  - when: Debugging app preferences on macOS — answers "where is this setting actually coming from" instead of guessing across layers, or finding the right preference domain by partial name
- [skills/tmuxcap/SKILL.md](skills/tmuxcap/SKILL.md)
  - what: Capture tmux pane content and export as text, HTML, SVG, PNG, or JPG. Renders ANSI colors faithfully; raster modes use a headless browser to rasterize the HTML
  - when: Sharing terminal state with the user, feeding session output to an AI as context, or archiving a snapshot before it scrolls off — pick the right format per channel (paste vs. ticket vs. doc)
- [skills/shell-helper/SKILL.md](skills/shell-helper/SKILL.md)
  - what: Project root detection (walks up looking for `.git`, `package.json`, etc.), project name inference, and editor launching at the project root. Library used by other skills, not a standalone CLI
  - when: Writing another skill or script that needs to anchor commands at the right working directory — avoids re-implementing "find the project root" in every tool
- [skills/browser/SKILL.md](skills/browser/SKILL.md)
  - what: Interactive browser automation via Chrome DevTools Protocol — persistent or one-shot sessions, screenshots, JS eval, readable content extraction, network capture, and pluggable site-specific flows
  - when: The task requires a real visible browser (login, captcha, complex SPA), the user wants to interact with the page directly, or you need to drive a webui via `__tap__` from an agent loop
- [skills/browser/plugins/chatgpt/](skills/browser/plugins/chatgpt/)
  - what: ChatGPT plugin for the browser skill — capture conversations, threads, shared chats, and project chats from a logged-in `chatgpt.com` session via DOM extraction and the internal API
  - when: Scraping or archiving the user's ChatGPT history, exporting a specific conversation for reference, or driving an automated ChatGPT session inside an outer agent loop
- [skills/aiquota/SKILL.md](skills/aiquota/SKILL.md)
  - what: Report remaining Claude Code (5h rolling window) and Codex (7d rolling window) quota by reading local OAuth token state and parsing the provider's quota responses
  - when: The user asks how much agent budget is left, or before scheduling a long task that might blow the rate-limit window mid-run
- [skills/cloudflare-tunnel/SKILL.md](skills/cloudflare-tunnel/SKILL.md)
  - what: Manage Cloudflare Tunnel ingress rules and DNS records via the `cloudflared` CLI plus the Cloudflare API — add/remove subdomains, point them at local ports, list current routes
  - when: Exposing a local dev port to the internet at a stable subdomain — sharing a preview, hosting an OAuth callback, or testing webhooks. Pass actual port numbers (numeric hashids get misread as ports)
- [skills/imagegen/SKILL.md](skills/imagegen/SKILL.md)
  - what: AI image generation with OpenAI (gpt-image-1) and Gemini (imagen) providers — generate, edit, or remix images from text prompts and reference images. Single CLI; provider picked per command
  - when: The user wants an image asset (mockup, illustration, manipulation of an existing image, variation on a reference) without leaving the agent loop or opening a separate tool
- [skills/resend/SKILL.md](skills/resend/SKILL.md)
  - what: Send transactional email via the Resend API — single CLI that takes recipient, subject, and body (markdown or HTML), uses the user's verified sender domain, returns the Resend message ID
  - when: The agent needs to deliver output to the user (or anyone) by email — daily digests, scheduled report drops, async notifications, or any "email me when done" workflow
- [skills/text-copyedit/SKILL.md](skills/text-copyedit/SKILL.md)
  - what: Copy-edit text — fix grammar, tighten prose, or rewrite a blob into a concise listicle. Two modes (grammar pass vs. listicle conversion); preserves the user's voice and never adds new claims
  - when: Polishing the user's drafts, notes, or outbound writing without rewriting substance — or compressing a wordy paragraph into scannable bullets for a doc or message
- [skills/readme/SKILL.md](skills/readme/SKILL.md)
  - what: Canonical-README discipline — one README per directory with SKILL-compat frontmatter and SKILL.md symlink, every covered item graded AAA/AA/A (inlined / digested+pointer / pointer), size budget forces the ranking
  - when: Writing a new README from scratch or updating an existing one after code changes — gives the grade rubric, the frontmatter+symlink recipe, and the git-log-subpath incremental workflow
- [skills/dotfiles/SKILL.md](skills/dotfiles/SKILL.md)
  - what: DotfileStow — the symlink manager that processes `dotfiles/` into `$HOME`. Plain files symlink directly, `.tmpl` files render with `[vars]` from `.dotfiles.toml`, `.symlink` files become relative symlinks
  - when: Adding new dotfiles to the repo, debugging why a symlink/template didn't materialize as expected, or resolving a "skipped due to conflict" message after running `pymake dotfiles`

## Opensource Tools

Distilled use cases for complex third-party tools. Recipe collections, not man-page rewrites. Empty for now.

## Research Notes

High-level mental models — "how does X actually work". Empty for now; populate by promoting durable notes out of `$MDNOTES_ROOT`.

## Design Specs

Durable design documents for the user's own systems.

- [docs/dotfile-stow-design.md](docs/dotfile-stow-design.md)
  - what: Design of DotfileStow — how `.tmpl`, `.symlink`, and plain files resolve into `$HOME`, conflict handling, and the rationale for replacing chezmoi
  - when: Modifying `dotfile_stow.py`, debugging why a file did or didn't symlink as expected, or designing new file-handling conventions for the dotfiles repo — keeps changes aligned with the original spec
