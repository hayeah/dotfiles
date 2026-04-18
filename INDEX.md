# INDEX

Wiki-style entry point. Awesome-list of pointers — content lives in the
linked docs, not here. Maintenance conventions: [skills/indexmd/SKILL.md](skills/indexmd/SKILL.md).

> **Format pilot.** Coding Conventions and Design Specs are in the new
> flat `what:` / `when:` shape. Personal Tools below the marker still
> needs the same rewrite.

## Coding Conventions

Cross-language conventions and language-specific style guides.

- [libs/README.md](libs/README.md)
  - what: Index README for the cross-language convention libraries —
    same canonical primitives ported across Python, TypeScript, and Go.
    Python is the reference; shared test vectors in `libs/testdata/` keep
    all three ports byte-identical
  - when: Picking among the lib modules, or adding a new
    cross-language primitive — explains import paths, the
    reference-implementation rule, and the test-vector contract that
    every port must satisfy
- [libs/hayeah-py/src/hayeah/core/logger/](libs/hayeah-py/src/hayeah/core/logger/)
  - what: Structured logging — colored console output to stderr plus
    a JSONL file at `~/.local/log/<tool>.jsonl` with 5MB rotation and 3
    backups. `LOG_LEVEL` (debug/info/warn/error, default info) controls
    verbosity. Same shape in py/ts/go
  - when: Adding logging to any of the user's CLIs or tools — gives
    uniformly tail-able JSONL alongside readable terminal output. Skip
    `logging.basicConfig`, don't roll your own, and prefer this even
    for one-off scripts that might grow legs
- [libs/hayeah-py/src/hayeah/core/fzfmatch/](libs/hayeah-py/src/hayeah/core/fzfmatch/)
  - what: Non-interactive deterministic fuzzy filter using fzf's
    term syntax — `!neg` excludes, `'word` is word-boundary, `^prefix`
    and `suffix$` anchor, space is AND, `;` is OR, `|` is
    lower-precedence AND. Boolean match, no scoring
  - when: Filtering a list of strings (paths, resource names, IDs) by a
    user-supplied expression and you want fzf semantics without
    spawning fzf — e.g. backing a `<cli> ls --filter "src .py !test"`
    style flag inside a CLI
- [libs/hayeah-py/src/hayeah/core/config/](libs/hayeah-py/src/hayeah/core/config/)
  - what: Single env-var config loader — `<APP>_CONFIG` is either a
    JSON literal or a `.json`/`.toml` path (detected by extension).
    Bundles `expand_env` for `${VAR}` interpolation with bash-style
    `${VAR:-default}` fallbacks
  - when: Picking a config approach for any of the user's apps so they
    all share one knob (`<APP>_CONFIG`) and the same env-expansion
    semantics — avoids per-app YAML/dotenv reinvention and keeps
    container deploys to a single env var
- [libs/hayeah-py/src/hayeah/core/shortid/](libs/hayeah-py/src/hayeah/core/shortid/)
  - what: Two standalone functions — `generate` makes a random
    human-friendly ID (3–8 chars, alphabet `0-9a-z` minus `l` and `o`)
    unique within a set; `resolve` matches a query against any string
    set by shortest unambiguous prefix
  - when: Assigning user-facing handles (sessions, tasks, services) the
    user will type back, or accepting partial UUIDs/SHAs as identifiers
    — gives `git`-style prefix resolution without the ambiguity
    surprises of a naive `startswith`
- [libs/hayeah-py/src/hayeah/core/lstree/](libs/hayeah-py/src/hayeah/core/lstree/)
  - what: Directory walker with `.gitignore` support, builtin
    ignores for ecosystem junk (`node_modules`, `__pycache__`, `.venv`
    …), and a three-stage filter pipeline: base exclude → include globs
    → additional exclude. Port of `go-lstree`
  - when: Scanning a project tree for files (build inputs, manifest
    discovery, source enumeration) and you need behavior matching
    `git ls-files` plus glob narrowing — without pulling in a
    heavyweight fs walker dependency
- [skills/swiftui/SKILL.md](skills/swiftui/SKILL.md)
  - what: SwiftUI development — SPM+XcodeGen project setup, the global
    state tree pattern, and the SwiftUITap agent SDK for driving a
    running SwiftUI app from outside the simulator
  - when: Starting or working on a native iOS/macOS SwiftUI app —
    picks up the user's project shape, state architecture, and the
    agent-driven test setup instead of generic Apple-template defaults
- [skills/swiftui/guides/swiftui-state.md](skills/swiftui/guides/swiftui-state.md)
  - what: Global state tree pattern for SwiftUI — single observable
    root with domain-grouped child stores, observed via property
    wrappers across the view hierarchy. Direct sets for single writes;
    action methods for multi-property
  - when: Designing or extending the state model for a SwiftUI app, or
    deciding where a piece of state should live (root vs. child store)
    and how views should observe it without prop-drilling
- [skills/swiftui/guides/swiftui-tap.md](skills/swiftui/guides/swiftui-tap.md)
  - what: SwiftUITap agent SDK — programmatic tap, inspect, and assert
    against a running SwiftUI app from outside the simulator. Lets
    agents drive iOS/macOS UIs end-to-end without XCUITest
  - when: Setting up agent-driven UI tests for a SwiftUI app, or
    building tooling that needs to interact with a running app from an
    outer agent loop (visual regression, E2E flows, demos)
- [skills/swiftui/guides/xcodegen-spm-first.md](skills/swiftui/guides/xcodegen-spm-first.md)
  - what: SPM-first project layout generated by XcodeGen —
    `Package.swift` is the source of truth for code/deps while
    XcodeGen produces a working `.xcodeproj` for IDE-only features
    (entitlements, schemes, signing)
  - when: Scaffolding a new SwiftUI project, or migrating an
    Xcode-managed project so modules and dependencies live in
    `Package.swift` instead of being trapped inside the `.xcodeproj`

- [skills/golang/SKILL.md](skills/golang/SKILL.md)
  - what: Go style guide — project structure (root SDK package + `cli/`
    subdir), CLI parsing rules (stdlib `flag` only, no cobra/urfave),
    naming, error handling, and the conventions the user expects in
    every Go project
  - when: Writing or reviewing Go code in any of the user's repos —
    catches "wrong CLI lib", "internal pkg without reason", "wrong
    layout" before they land
- [skills/golang/wire.md](skills/golang/wire.md)
  - what: Reference for `google/wire` (and the maintained `goforj/wire`
    fork) — provider sets, bindings, value/struct/interface providers,
    cleanup funcs, and the generated initializer flow
  - when: Wiring up dependencies in a Go service (DB, repos, handlers)
    where you want compile-time DI without runtime reflection — or
    debugging a `wire_gen.go` that won't compile
- [skills/python/SKILL.md](skills/python/SKILL.md)
  - what: Python coding conventions — `uv` + `pyproject.toml` project
    layout, ruff/pyright/pytest tooling, typer for CLIs (`uv tool
    install -e .`), and src-layout for proper internal imports
  - when: Bootstrapping a new Python project, refactoring an existing
    one to the user's stack, or deciding which tools/libraries to reach
    for instead of guessing
- [skills/python/pymake.md](skills/python/pymake.md)
  - what: Drop-in `Makefile.py` template for `hayeah/pymake` — typical
    `lint`, `typecheck`, `format`, `test`, and `default` task
    definitions plus the `sh()` + `@task()` patterns
  - when: Adding a `Makefile.py` to a Python project, or extending an
    existing one with new tasks — start from the template instead of
    re-deriving the conventions
- [skills/python/notebook.md](skills/python/notebook.md)
  - what: Jupyter percent-format conventions — `.py` files with `# %%`
    cell delimiters, parameters cell tagging, jupytext header — so
    notebooks stay version-control friendly and diff-able as plain
    Python
  - when: Authoring or editing a notebook in any of the user's
    projects, or deciding how to structure exploratory analysis you
    want to commit alongside source
- [skills/typescript/SKILL.md](skills/typescript/SKILL.md)
  - what: TypeScript style guide and tooling — vite/vitest for build,
    oxfmt/oxlint for lint, bun as default runtime, mobx for complex
    state, plus class conventions (parameter properties, static async
    factories instead of `init`)
  - when: Writing or reviewing TypeScript in any of the user's repos,
    or scaffolding a new TS project — picks up the user's toolchain
    and class style instead of generic eslint/prettier defaults
- [skills/react/SKILL.md](skills/react/SKILL.md)
  - what: React project conventions — Vite + React + TS + Tailwind +
    wouter + MobX + Framer Motion stack, scaffold commands, vite
    config, file organization, and the MobX/tap testing patterns
  - when: Scaffolding a new React app, or modifying an existing one
    where you need to know the user's stack picks (routing, state,
    animation) and component layout before adding files
- [skills/webui/SKILL.md](skills/webui/SKILL.md)
  - what: Web UI workflow — Vite+ (`vp`) toolchain, explicit-port dev
    server, page-grouped file layout, browser-skill-driven E2E
    testing, MobX global state, `__tap__` API, and `/preview` route
    pattern
  - when: Working on a web UI where the agent needs to drive the page
    via screenshots + JS eval (state changes, regression checks) and
    the project follows the user's Vite+/MobX/tap conventions
- [skills/webui/guides/viteplus.md](skills/webui/guides/viteplus.md)
  - what: Comprehensive reference for Vite+ (vite.plus) — the unified
    `vp` CLI from VoidZero that bundles Vite, Vitest, Oxlint, Oxfmt,
    Rolldown, tsdown, and Vite Task. Install, scaffold, dev/build/test
    commands
  - when: Setting up a project on Vite+ or running into a `vp`
    subcommand whose behavior isn't obvious — single source of truth
    instead of digging through five separate tool docs
- [skills/webui/guides/libraries.md](skills/webui/guides/libraries.md)
  - what: Recommended libraries for React web UI projects — Tailwind v4
    + clsx/cn + cva, lucide icons, framer-motion, dnd-kit, cmdk,
    embla, plus picks for data, forms, charting, and UI primitives
  - when: Picking a library for a recurring need (carousel, command
    palette, drag-and-drop, charts) so the choice matches the rest of
    the user's web stack instead of pulling in a one-off
- [skills/webui/guides/mobx-global-state.md](skills/webui/guides/mobx-global-state.md)
  - what: MobX global state pattern — one observable `AppStore` tree
    with domain-grouped child stores, observed via `observer()`.
    Direct sets for single writes, action methods for multi-property,
    `__DOC__` on the root, no wrapper setters
  - when: Designing or extending state in a React/MobX app, or
    deciding whether a piece of state belongs in the global tree
    versus `useState` — `useState` is reserved for ephemeral
    view-local state only
- [skills/webui/guides/web-tap-api.md](skills/webui/guides/web-tap-api.md)
  - what: `window.__tap__` convention — expose app state, callbacks,
    and DOM refs (with `$` prefix) so the agent drives the page via
    `browser eval` instead of clicking. `__DOC__` constant documents
    the surface
  - when: Building or extending a web UI you'll want to drive from an
    agent loop — designing the tap API up front beats trying to
    automate it later via fragile DOM selectors
- [skills/webui/guides/preview-route.md](skills/webui/guides/preview-route.md)
  - what: `/preview` route pattern — render the live view tree against
    a `MockDataSource` so UI iterates without the backend. Mock
    mutators on `__tap__` let the agent drive any state via
    `browser eval`
  - when: Iterating on UI for a feature whose backend is slow,
    flaky, or unbuilt — or when you want a stable surface for visual
    regression and agent-driven E2E without spinning up real services
- [skills/webui/guides/webui-template.md](skills/webui/guides/webui-template.md)
  - what: README for the `hayeah/webui-template` scaffold — Vite+,
    React, TS, Tailwind v4, MobX, wouter, framer-motion, OKLCh design
    tokens with light/dark mode. Includes `/design` and
    `/design/dashboard` sample pages
  - when: Starting a new web UI from scratch, or pulling specific
    pieces (theme tokens, auth shell, design pages) from the template
    into an existing project

## Personal Tools

Tools the user built — unlikely to be in agent training sets, so the
link is load-bearing.

- [pymake](https://github.com/hayeah/pymake)
  - what: Python Makefile alternative — declare tasks in
    `Makefile.py`, deps tracked via `tree_digest` so unchanged subtrees
    skip rebuilds. Parallel execution by default
  - when: Build, setup, or refresh pipelines in any of the user's
    projects — especially when you want incremental rebuilds based on
    file content (`tree_digest`) rather than mtime, with parallel
    execution out of the box
- [skills/mdnote/](skills/mdnote/SKILL.md)
  - what: Create dated markdown notes in
    `$MDNOTES_ROOT/<date>/<title>_<agent>.md` with YAML frontmatter
    (overview, repo, tags). The dumping ground for ad-hoc research
  - when: Producing research, design chatter, or notes worth keeping
    past the conversation — anything more durable than `tmpfile`
    scratch but not yet promoted into INDEX.md as a wiki entry

<!-- TODO: rewrite remaining Personal Tools entries in flat what/when shape -->
- [devportv2](https://github.com/hayeah/devportv2) — dev service supervisor with stable port assignment, health checks, tmux processes
- [godzkilla](https://github.com/hayeah/godzkilla) — install/sync agent skills into `~/.claude/skills/`, `~/.codex/skills/`, `~/.openclaw/skills/`
- [duckql](https://github.com/hayeah/duckql) — DuckDB-as-a-pipe for the `ls` convention
- [agentboss](https://github.com/hayeah/agentboss) — tmux-based supervisor for interactive CLIs (claude code, codex, repls)
- [oauth-ai](https://github.com/hayeah/oauth-ai) — CLI-first OAuth toolkit for AI providers
- [skills/gobin/](skills/gobin/SKILL.md) — `uv tool install -e` for go CLIs via build shim
- [skills/git-quick-clone/](skills/git-quick-clone/SKILL.md) — treeless partial clone into `$GITHUB_REPOS`
- [skills/ctrlv/](skills/ctrlv/SKILL.md) — dump macOS clipboard (text / image / file) into `.ctrlv/`
- [skills/dotenv-ls/](skills/dotenv-ls/SKILL.md) — list env var names without exposing values
- [skills/jsoninspect/](skills/jsoninspect/SKILL.md) — pretty-print JSON/JSONL with string truncation
- [skills/plist/](skills/plist/SKILL.md) — layered macOS plist inspection + fuzzy domain search
- [skills/tmuxcap/](skills/tmuxcap/SKILL.md) — capture tmux pane as text / html / svg / png / jpg
- [skills/shell-helper/](skills/shell-helper/SKILL.md) — project root detection + editor launching
- [skills/browser/](skills/browser/SKILL.md) — chrome DevTools Protocol browser automation
  - [plugins/chatgpt](skills/browser/plugins/chatgpt/) — chatgpt plugin
- [skills/aiquota/](skills/aiquota/SKILL.md) — report remaining claude code + codex quota
- [skills/cloudflare-tunnel/](skills/cloudflare-tunnel/SKILL.md) — manage tunnel ingress + DNS
- [skills/imagegen/](skills/imagegen/SKILL.md) — openai + gemini image generation
- [skills/resend/](skills/resend/SKILL.md) — send email via resend API
- [skills/text-copyedit/](skills/text-copyedit/SKILL.md) — grammar fix / listicle tidy
- [skills/readme-skill/](skills/readme-skill/SKILL.md) — generate agent-friendly SKILL.md
- [skills/create-role/](skills/create-role/SKILL.md) — bundle skills into a role persona
- [skills/dotfiles/](skills/dotfiles/SKILL.md) — dotfile_stow.py symlink manager
- [skills/indexmd/](skills/indexmd/SKILL.md) — how to maintain this INDEX.md

## Opensource Tools

Distilled use cases for complex third-party tools. Recipe collections,
not man-page rewrites.

- [skills/chezmoi/](skills/chezmoi/) — chezmoi reference

## Research Notes

High-level mental models — "how does X actually work". Empty for now;
populate by promoting durable notes out of `$MDNOTES_ROOT`.

## Design Specs

Durable design documents for the user's own systems.

- [docs/dotfile-stow-design.md](docs/dotfile-stow-design.md)
  - what: Design of DotfileStow — how `.tmpl`, `.symlink`, and
    plain files resolve into `$HOME`, conflict handling, and the
    rationale for replacing chezmoi
  - when: Modifying `dotfile_stow.py`, debugging why a file did or
    didn't symlink as expected, or designing new file-handling
    conventions for the dotfiles repo — keeps changes aligned with the
    original spec
