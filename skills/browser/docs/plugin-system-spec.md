---
overview: Design spec for browser eval plugin system — Vite-built, URL-scoped plugins with multi-module route matching, --node flag for Node eval context, --expect flag, and per-plugin SKILL.md for agent discovery.
repo: /Users/me/github.com/hayeah/dotfiles/skills/browser
tags:
  - spec
---

# Browser Eval Plugin System — Design Spec

## Problem

`browser eval` runs raw JS in a page context. For recurring tasks on specific sites (ChatGPT, GitHub, Linear, etc.), agents and humans re-write the same boilerplate: finding DOM elements, extracting structured data, calling site-specific APIs.

We want a **plugin** layer that injects high-level helper objects into the eval scope — like Greasemonkey userscripts, but for CLI-driven browser automation.

## Goals

- **Grab-bag of helpers**: Each plugin exports functions, classes, constants — whatever's useful for that site
- **URL-scoped with route matching**: Plugins declare URL patterns; different paths within a site can load different modules
- **Autoloading**: When eval runs on a matching page, the relevant module loads automatically
- **Self-documenting**: An agent can discover what plugins exist and what they provide
- **Composable**: Multiple plugins can load on the same page (e.g. `dom` + `github`)
- **Vite-powered**: Use Vite's library mode for bundling browser modules from TypeScript into IIFE bundles
- **Two eval modes**: `browser eval` (browser context) and `browser eval --node` (Node context) — cleanly separated, each with their own plugin modules
- **Stateless per-eval**: Browser plugins are fresh on every eval call — no persistent state complexity
- **`--expect` for scripting**: Block eval return until a condition is true, like the `expect` terminal tool

## Non-Goals

- Plugin package manager / versioning (just files on disk)
- Persistent background scripts (plugins are injected per-eval, not long-running)
- Workflow DSL (agents compose with sequential `browser` commands)
- Cross-plugin dependencies (each plugin is self-contained)
- Framework-managed `exposeFunction` bridging (plugin authors call it explicitly if needed)

---

## `--expect`: Block Until Condition

### Motivation

Multi-step browser automation needs to **wait for state** before proceeding. Currently you'd write:

```bash
# Clumsy: eval a polling loop inside the browser
browser eval '(async () => {
  while (!document.querySelector(".loaded")) await new Promise(r => setTimeout(r, 500));
  return document.querySelector(".loaded").textContent;
})()'
```

This is the same pain point Greasemonkey users hit — every script reinvents `waitForElement`. The terminal `expect` tool solved this for shell scripting: "wait until you see this pattern, then continue."

### Design

`--expect` is a flag on `browser eval` that takes a JS expression. Eval re-runs the main code repeatedly until the expect condition returns truthy on the result.

```bash
# Block until messages() returns a non-empty array
browser eval --expect 'result.length > 0' 'chatgpt.messages()'

# Block until an element exists, return its text
browser eval --expect 'result !== null' 'document.querySelector(".response")?.textContent'

# With timeout (default: 30s)
browser eval --expect 'result.status === "done"' --timeout 10 'api.pollStatus()'
```

### Semantics

```
browser eval --expect <condition> [--timeout <seconds>] [--interval <ms>] <code>
```

- **`<condition>`**: JS expression evaluated in Node.js. The variable `result` is bound to the return value of `<code>`
- **`--timeout`**: Max wait time in seconds (default: 30). Exit code 1 on timeout
- **`--interval`**: Poll interval in ms (default: 500)
- **Behavior**: Run `<code>` in browser via `page.evaluate`. Check `<condition>` against result. If falsy, sleep `interval` ms, re-run. On truthy, print result and exit 0. On timeout, print last result to stderr and exit 1

### Why Node-Side, Not Browser-Side

The condition runs in Node.js on the serialized result, not inside the browser. This keeps it simple:
- No MutationObserver complexity
- No need to wire up in-browser polling
- Each poll iteration is a fresh `page.evaluate` — picks up DOM changes, re-injects plugins
- Result is always JSON-serializable (same as regular eval)

The tradeoff is latency: each poll round-trips through CDP. For most automation tasks, 500ms polling is fine. If sub-100ms responsiveness matters, use `page.waitForFunction` directly in a script file.

### Interaction with Plugins

Plugins are re-injected on each poll iteration. This is correct — the page may have changed between polls (SPA navigation, dynamic content). The plugin object is always fresh.

```bash
# Plugins autoload on each iteration
browser eval --expect 'result.length > 0' 'chatgpt.messages()'

# Explicit plugin loading also works
browser eval --plugin chatgpt --expect 'result.length > 0' 'chatgpt.messages()'
```

### `--expect` works with `--node` too

```bash
# Poll a Node-side operation
browser eval --node --expect 'result.status === "ready"' 'await chatgpt.pollExport()'
```

### Composing `--expect` in Workflows

```bash
# Agent-driven multi-step workflow:

# Navigate
browser nav "https://chatgpt.com/c/abc123"

# Wait for conversation to load (expect blocks until ready)
browser eval --expect 'result.length > 0' 'chatgpt.messages()'

# Send a message
browser eval 'chatgpt.send("Summarize this conversation")'

# Wait for response to complete
browser eval --expect 'result === true' 'chatgpt.isResponseComplete()'

# Extract the response
browser eval 'chatgpt.lastResponse()'

# Save to file (Node context)
browser eval --node 'await chatgpt.save("/tmp/conversation.json")'
```

This replaces the need for `browser wait-for` as a separate command — `--expect` on eval is more powerful because it returns the value once the condition is met.

### `browser wait` (Human-in-the-Loop)

Still useful as a separate command for pausing until human input:

```bash
browser wait "Please log in, then press Enter"
```

Reads a line from stdin. Prints the message to stderr. Simple.

---

## Plugin Architecture

### Plugin Directory Layout

Each plugin is a directory with a `plugin.json` manifest, one or more browser/node modules, and agent-facing docs:

```
skills/browser/plugins/
├── chatgpt/
│   ├── plugin.json              # Manifest: routes, patterns, modules
│   ├── SKILL.md                 # Agent-facing docs
│   ├── package.json             # Plugin's own deps (if any)
│   ├── vite.config.ts           # Vite build config
│   ├── src/
│   │   ├── conversation.ts      # Browser module for /c/* pages
│   │   ├── conversation.node.ts # Node module for /c/* pages
│   │   ├── share.ts             # Browser module for /share/* pages
│   │   └── common.ts            # Browser module for all chatgpt.com pages
│   └── dist/
│       ├── conversation.iife.js # Built browser modules
│       ├── share.iife.js
│       └── common.iife.js
├── github/
│   ├── plugin.json
│   ├── ...
└── dom/
    ├── ...
```

User plugins override built-in ones:

```
~/.config/browser-plugins/
├── my-custom-plugin/
│   ├── plugin.json
│   ├── SKILL.md
│   └── ...
```

Scan order: `skills/browser/plugins/` first, then `~/.config/browser-plugins/`. On name collision, user plugin wins.

### plugin.json

The manifest defines the plugin name and a list of **routes** — URL patterns mapped to modules. Routes are evaluated top-to-bottom; **first match wins** (waterfall).

```json
{
  "name": "chatgpt",
  "description": "Helpers for interacting with ChatGPT web UI",
  "routes": [
    {
      "match": ["*://chatgpt.com/c/*"],
      "browser": "src/conversation.ts",
      "node": "src/conversation.node.ts"
    },
    {
      "match": ["*://chatgpt.com/share/*"],
      "browser": "src/share.ts"
    },
    {
      "match": ["*://chatgpt.com/*"],
      "browser": "src/common.ts"
    }
  ]
}
```

- **name**: Plugin identifier. Becomes the variable name in eval scope
- **description**: One-line summary for `browser plugins` listing
- **routes**: Ordered list of route rules. First matching route wins
  - **match**: URL patterns (Chrome @match syntax). Array of patterns (any must match)
  - **exclude** (optional): URL patterns to skip
  - **browser** (optional): Path to browser-side module source (Vite-built to IIFE)
  - **node** (optional): Path to Node-side module source

A route can have `browser` only, `node` only, or both.

A plugin with no routes (or empty `match`) is manual-only — load via `--plugin`.

### Why Waterfall (First Match Wins)

A single plugin for `chatgpt.com` might have very different helpers for `/c/*` (conversations), `/share/*` (shared links), and `/s/*` (posts). These are essentially different apps under one domain.

Waterfall matching keeps it simple:
- No ambiguity about which modules loaded
- No merging conflicts between route modules
- If the `/c/*` module needs common helpers, it imports them internally (Vite bundles the shared code)
- More specific routes go first, generic catch-all at the bottom

### URL Pattern Matching

Chrome's `@match` pattern syntax (same as Greasemonkey — proven, well-understood):

```
<scheme>://<host>/<path>
```

- **Scheme**: `http`, `https`, `*` (both)
- **Host**: exact domain, `*.example.com` (subdomains), `*` (all)
- **Path**: literal with `*` as wildcard

Examples:
```
*://chatgpt.com/c/*         # Conversation pages
*://chatgpt.com/share/*     # Shared links
*://*.github.com/*           # GitHub + subdomains
https://linear.app/team/*    # Linear, specific path prefix
```

---

## Two Eval Contexts

The `--node` flag switches eval from browser context to Node context. Each context has its own plugin modules and available globals. The framework doesn't bridge between them — they are cleanly separated.

```bash
# Browser context (default) — runs inside page.evaluate
browser eval 'chatgpt.messages()'

# Node context — runs in Node.js with page/browser available
browser eval --node 'await chatgpt.save("/tmp/msgs.json")'
browser eval --node 'await page.screenshot({path: "/tmp/page.png"})'
```

### Browser Modules (default eval)

Browser modules run inside `page.evaluate`. They have DOM access and are the primary plugin mechanism.

**Source** (`src/conversation.ts`):

```typescript
export default function setup() {
  function messages() {
    const turns = document.querySelectorAll("[data-message-id]");
    return Array.from(turns).map((el) => ({
      id: el.getAttribute("data-message-id"),
      role: el.querySelector(".agent-turn") ? "assistant" : "user",
      text: el.textContent?.trim() ?? "",
    }));
  }

  function lastResponse() {
    const msgs = messages();
    const last = msgs.filter((m) => m.role === "assistant").at(-1);
    return last?.text ?? null;
  }

  function isResponseComplete() {
    return document.querySelector('[data-testid="stop-button"]') === null;
  }

  return { messages, lastResponse, isResponseComplete };
}
```

Key rules:
- Default export is a **setup function** — called at injection time, returns the API object
- Can import other local files — Vite bundles them
- Can import npm packages — Vite bundles them
- **Cannot** use Node.js APIs (no `fs`, `path`, etc.)
- Return value must be a plain object of functions/values

**Build output**: Vite library mode produces an IIFE:

```javascript
var __browserPlugin = (function() {
  "use strict";
  function setup() {
    // ... bundled code ...
    return { messages, lastResponse, isResponseComplete };
  }
  return setup;
})();
```

### Node Modules (`--node` eval)

Node modules run in Node.js. They receive `{page, browser}` and return an API object — same setup pattern as browser modules, different context.

**Source** (`src/conversation.node.ts`):

```typescript
import type { Page, Browser } from "puppeteer-core";
import { writeFileSync } from "node:fs";

export default async function setup({ page, browser }: { page: Page; browser: Browser }) {
  return {
    async save(path: string) {
      const msgs = await page.evaluate(() => {
        const turns = document.querySelectorAll("[data-message-id]");
        return Array.from(turns).map((el) => ({
          id: el.getAttribute("data-message-id"),
          role: el.querySelector(".agent-turn") ? "assistant" : "user",
          text: el.textContent?.trim() ?? "",
        }));
      });
      writeFileSync(path, JSON.stringify(msgs, null, 2));
    },

    async screenshot(selector: string, path: string) {
      const el = await page.$(selector);
      if (!el) throw new Error(`Element not found: ${selector}`);
      await el.screenshot({ path });
    },

    async downloadImage(url: string, path: string) {
      const res = await fetch(url);
      const buf = Buffer.from(await res.arrayBuffer());
      writeFileSync(path, buf);
    },
  };
}
```

Key rules:
- Default export is an **async setup function** — receives `{page, browser}`, returns the API object
- Regular TypeScript module — no Vite build needed, loaded via dynamic import
- Has full Node.js access: `fs`, `path`, `fetch`, env vars, child processes
- Has full Puppeteer access: `page.evaluate()`, `page.$()`, `page.screenshot()`, CDP sessions
- If the plugin author wants to bridge a function into browser context, they call `page.exposeFunction()` explicitly in setup — the framework doesn't do this automatically

### Injection: Function Parameters, Not Window Globals

Both contexts inject plugins as **function parameters** to the eval wrapper, not as `window.*` globals.

#### Browser eval injection

The current eval wraps user code in an `AsyncFunction`:

```typescript
// Current:
new AsyncFunction(`return (${code})`)()
```

With plugins, the wrapper passes plugin objects as named parameters:

```typescript
// With plugins:
const fn = new AsyncFunction('chatgpt', 'dom', `return (${code})`);
fn(chatgptObj, domObj);
```

**Full browser injection flow:**

```typescript
async function evalBrowser(page: Page, code: string, plugins: LoadedBrowserPlugin[]) {
  const names: string[] = [];
  const iifeSources: string[] = [];

  for (const plugin of plugins) {
    names.push(plugin.name);
    iifeSources.push(readFileSync(plugin.iifeDistPath, "utf-8"));
  }

  return page.evaluate(
    (code: string, names: string[], sources: string[]) => {
      // Instantiate each plugin by executing its IIFE and calling setup()
      const pluginObjects = sources.map((src) => {
        const setup = new Function(`${src}; return __browserPlugin;`)();
        return typeof setup === "function" ? setup() : setup;
      });

      // Build and call the user's code with plugins as named parameters
      const AsyncFunction = (async () => {}).constructor as any;
      const fn = new AsyncFunction(...names, `return (${code})`);
      return fn(...pluginObjects);
    },
    code, names, iifeSources,
  );
}
```

#### Node eval injection

Same pattern, but runs in Node.js. `page` and `browser` are always available as parameters alongside any node plugin objects.

```typescript
async function evalNode(
  page: Page,
  browser: Browser,
  code: string,
  plugins: LoadedNodePlugin[],
) {
  // Setup each node plugin
  const names = ["page", "browser"];
  const objects: any[] = [page, browser];

  for (const plugin of plugins) {
    const mod = await import(plugin.nodeModulePath);
    const api = await mod.default({ page, browser });
    names.push(plugin.name);
    objects.push(api);
  }

  // Eval the code with all plugins + page/browser as parameters
  const AsyncFunction = (async () => {}).constructor as any;
  const fn = new AsyncFunction(...names, code);
  return fn(...objects);
}
```

Usage:

```bash
# page and browser are always available in --node context
browser eval --node 'await page.screenshot({path: "/tmp/page.png"})'
browser eval --node 'page.url()'

# Plugin methods are also available
browser eval --node 'await chatgpt.save("/tmp/msgs.json")'
browser eval --node 'await chatgpt.screenshot(".message:last-child", "/tmp/last.png")'

# Mix page access with plugin helpers
browser eval --node '
  const url = page.url();
  await chatgpt.save(`/tmp/${url.split("/").pop()}.json`);
'
```

Note: `--node` eval code uses bare statements (not expression-wrapped) since Node-side code is more likely to be multi-statement. The return value is the last expression, or explicitly `return`ed.

### exposeFunction — Plugin Author's Tool, Not Framework Magic

The framework does **not** automatically bridge node methods into browser context. If a plugin author wants browser eval code to call Node-side functions, they do it explicitly in their node module's setup:

```typescript
// src/conversation.node.ts
export default async function setup({ page, browser }) {
  // Explicitly bridge specific functions into browser context
  try {
    await page.exposeFunction("__chatgpt_save", async (path: string, data: string) => {
      writeFileSync(path, data);
    });
  } catch {
    // Already exposed on this page — skip
  }

  return {
    async save(path: string) { /* ... */ },
  };
}
```

Then browser eval code can call it directly:

```bash
browser eval 'await __chatgpt_save("/tmp/data.json", JSON.stringify(chatgpt.messages()))'
```

This is opt-in and explicit. The plugin author decides what to bridge, names it themselves, handles the lifecycle. The framework stays simple.

Most of the time, you don't need this — just use `--node` for Node-side work and default eval for browser-side work.

### Context Summary

| | Browser eval (default) | Node eval (`--node`) |
|---|---|---|
| **Runs in** | Browser (`page.evaluate`) | Node.js |
| **Plugin source** | `"browser"` field in route | `"node"` field in route |
| **Built with** | Vite library mode (IIFE) | Regular TS (dynamic import) |
| **Has access to** | DOM, window, fetch (page cookies) | page, browser, fs, env, CDP |
| **Plugin injection** | AsyncFunction params (no window globals) | AsyncFunction params (`page`, `browser` always included) |
| **Lifecycle** | Fresh per-eval (stateless) | Setup per-eval |
| **Return value** | JSON-serializable | Any (printed via formatResult) |

---

## Vite Build

Only browser modules need building. Node modules are loaded directly via dynamic import.

### Per-Plugin Config

Each plugin uses Vite's library mode. With multi-module routes, each browser module is a separate entry:

```typescript
// chatgpt/vite.config.ts
import { pluginViteConfig } from "../vite.plugin.config.js";
export default pluginViteConfig({
  entries: {
    conversation: "src/conversation.ts",
    share: "src/share.ts",
    common: "src/common.ts",
  },
});
```

### Shared Vite Config

```typescript
// skills/browser/plugins/vite.plugin.config.ts
import { defineConfig } from "vite";

export function pluginViteConfig(opts: {
  entries: Record<string, string>;
}) {
  return defineConfig({
    build: {
      rollupOptions: {
        input: opts.entries,
        output: {
          format: "iife",
          dir: "dist",
          entryFileNames: "[name].iife.js",
          name: "__browserPlugin",
        },
      },
      minify: false,
      emptyOutDir: true,
    },
  });
}
```

Each entry produces `dist/<name>.iife.js`. The `plugin.json` routes reference source paths; the host resolves them to built paths at runtime (e.g. `src/conversation.ts` → `dist/conversation.iife.js`).

### Build Workflow

```bash
# Build a single plugin
cd skills/browser/plugins/chatgpt && pnpm build

# Build all plugins
cd skills/browser/plugins && pnpm -r build
```

Plugins directory as a pnpm workspace:

```yaml
# skills/browser/plugins/pnpm-workspace.yaml
packages:
  - "*"
```

Each plugin's package.json:

```json
{
  "name": "@browser-plugins/chatgpt",
  "private": true,
  "scripts": { "build": "vite build" },
  "devDependencies": { "vite": "^6" }
}
```

---

## CLI Interface

### `browser eval` (extended)

```bash
# Browser context (default) — plugins inject DOM helpers
browser eval 'chatgpt.messages()'
browser eval --plugin chatgpt --plugin dom 'dom.select("h1")'
browser eval --no-plugins 'document.title'

# Node context — page/browser always available, plus node plugin helpers
browser eval --node 'await page.screenshot({path: "/tmp/page.png"})'
browser eval --node 'await chatgpt.save("/tmp/msgs.json")'
browser eval --node 'page.url()'

# --expect works in both contexts
browser eval --expect 'result.length > 0' 'chatgpt.messages()'
browser eval --node --expect 'result.ready' 'await chatgpt.checkExport()'

# Timeouts
browser eval --expect 'result !== null' --timeout 10 'document.querySelector(".done")?.textContent'
browser eval --expect 'result.length > 0' --interval 1000 'chatgpt.messages()'
```

Yargs options:

```typescript
interface EvalArgs {
  code: string;
  open?: string;
  session?: string;
  node?: boolean;               // --node (switch to Node eval context)
  plugin?: string[];            // --plugin (repeatable)
  "no-plugins"?: boolean;       // --no-plugins
  expect?: string;              // --expect <condition>
  timeout?: number;             // --timeout <seconds> (default: 30)
  interval?: number;            // --interval <ms> (default: 500)
}
```

### `browser plugins` (new command)

```bash
# List all available plugins
browser plugins

# List plugins matching a URL (shows which route matched)
browser plugins --url 'https://chatgpt.com/c/abc123'

# Show plugin details (metadata + SKILL.md)
browser plugins chatgpt

# Build all plugins
browser plugins build

# Build a specific plugin
browser plugins build chatgpt
```

Output examples:

```
$ browser plugins
NAME       ROUTES  DESCRIPTION
chatgpt    3       Helpers for ChatGPT web UI
github     2       GitHub PR/issue/repo helpers
dom        1       Generic DOM query utilities (manual only)

$ browser plugins --url 'https://chatgpt.com/c/abc123'
PLUGIN     ROUTE                    MODULES
chatgpt    *://chatgpt.com/c/*     browser + node

$ browser plugins chatgpt
Name: chatgpt
Description: Helpers for ChatGPT web UI
Path: /Users/me/.../skills/browser/plugins/chatgpt

Routes:
  *://chatgpt.com/c/*       → conversation (browser + node)
  *://chatgpt.com/share/*   → share (browser)
  *://chatgpt.com/*         → common (browser)

--- SKILL.md ---
[contents of SKILL.md]
```

### `browser wait` (new command)

```bash
browser wait "Please log in, then press Enter"
```

Prints message to stderr, reads a line from stdin. Returns the line (if any) to stdout.

---

## Plugin SKILL.md

Each plugin has a SKILL.md that agents read to understand the API. Methods document which eval context they belong to.

### Template

```markdown
# chatgpt

Available as `chatgpt` in `browser eval` scope.

## Routes

- `*://chatgpt.com/c/*` — conversation helpers (browser + node)
- `*://chatgpt.com/share/*` — shared link extraction (browser)
- `*://chatgpt.com/*` — common helpers (browser)

## Browser API (conversation route)

### chatgpt.messages()
Returns all conversation messages.
Returns: `Array<{id: string, role: "user" | "assistant", text: string}>`

### chatgpt.lastResponse()
Returns the text of the most recent assistant message.
Returns: `string | null`

### chatgpt.isResponseComplete()
Returns true when the assistant has finished streaming.
Returns: `boolean`

## Node API (conversation route, use with `--node`)

### await chatgpt.save(path)
Extracts messages and saves as JSON to disk.
- `path` — output file path

### await chatgpt.screenshot(selector, path)
Screenshots a DOM element to a file.
- `selector` — CSS selector
- `path` — output file path

Note: `page` and `browser` are always available in `--node` context.

## Examples

Get conversation:
    browser eval 'chatgpt.messages()'

Wait for messages to load:
    browser eval --expect 'result.length > 0' 'chatgpt.messages()'

Save conversation to file:
    browser eval --node 'await chatgpt.save("/tmp/msgs.json")'

Screenshot last message:
    browser eval --node 'await chatgpt.screenshot("[data-message-id]:last-child", "/tmp/last.png")'

Full workflow:
    browser nav "https://chatgpt.com/c/abc123"
    browser eval --expect 'result.length > 0' 'chatgpt.messages()'
    browser eval 'chatgpt.send("Summarize this")'
    browser eval --expect 'result === true' 'chatgpt.isResponseComplete()'
    browser eval --node 'await chatgpt.save("/tmp/summary.json")'
```

### Agent Integration

The browser SKILL.md gets a new section:

```markdown
## Plugins

Plugins inject site-specific helper objects into `browser eval` scope.

Discover available plugins:
    browser plugins
    browser plugins --url <url>

Read a plugin's API docs:
    browser plugins <name>

Plugins autoload when the page URL matches their routes.
Override with `--plugin <name>` or `--no-plugins`.

### --node (Node eval context)

Switch to Node.js eval context. `page` and `browser` are always available.
Node plugin modules provide helpers for file I/O, screenshots, CDP, etc.

    browser eval --node 'await page.screenshot({path: "/tmp/page.png"})'
    browser eval --node 'await chatgpt.save("/tmp/msgs.json")'

### --expect (blocking assertions)

Block until a condition on the eval result is truthy:
    browser eval --expect '<condition>' [--timeout <s>] [--interval <ms>] '<code>'

`result` is bound to the eval return value. Polls every 500ms (default), times out after 30s (default).
Works in both browser and node contexts.

    browser eval --expect 'result.length > 0' 'chatgpt.messages()'
    browser eval --expect 'result !== null' --timeout 10 'document.querySelector(".done")?.textContent'
```

---

## Resolved Decisions

| Question | Decision | Rationale |
|---|---|---|
| Plugin manifest format | `plugin.json` with routes array | Supports multi-module plugins; one plugin handles different paths on the same domain |
| Route matching | Waterfall (first match wins) | No ambiguity; specific routes first, catch-all last; shared code bundled by Vite |
| URL pattern syntax | Chrome @match style | Battle-tested in Greasemonkey/Tampermonkey ecosystem |
| Build system | Vite library mode (IIFE) for browser modules only | TypeScript + npm imports; node modules loaded directly via dynamic import |
| Browser injection | AsyncFunction parameters | No window pollution; `chatgpt` is a lexical variable, not `window.chatgpt` |
| Node injection | AsyncFunction parameters with `page`, `browser` always included | Same clean pattern; full Puppeteer access |
| Node ↔ browser bridging | Plugin author calls `page.exposeFunction()` explicitly if needed | Framework stays simple; no magic auto-bridging; most use cases don't need it |
| Browser plugin state | Stateless per-eval | Re-inject fresh each time; avoids persistent-state complexity |
| Node plugin state | Setup per-eval | Each `--node` eval imports and runs setup fresh |
| Dependencies between plugins | None | Self-contained; bundle shared helpers internally via Vite |
| Condition waiting | `--expect` on eval (both contexts) | More powerful than separate `wait-for` command; returns value on success |
| Expect evaluation | Node-side on serialized result | Avoids MutationObserver complexity; each poll re-runs eval fresh |
| Plugin scan directories | Built-in + user override | `skills/browser/plugins/` then `~/.config/browser-plugins/`; user wins on collision |

---

## Implementation Plan

### Phase 1: Plugin Loading + --expect

- `plugin.json` parsing with route matching
- URL pattern matcher (implement or use `micromatch`)
- Browser IIFE injection via AsyncFunction parameters (no window globals)
- `--plugin` and `--no-plugins` flags on eval
- `--expect`, `--timeout`, `--interval` flags on eval
- Shared Vite config for plugin builds
- pnpm workspace setup for plugins/

### Phase 2: --node Eval Context

- `--node` flag on eval command
- Node module loading via dynamic import
- `page` and `browser` injection as parameters
- Node plugin setup and injection alongside page/browser
- `--expect` support in node context

### Phase 3: Discovery & Docs

- `browser plugins` list command
- `browser plugins <name>` detail command (prints SKILL.md)
- `browser plugins --url <url>` filtering (shows matched route)
- `browser plugins build [name]` command
- Update browser SKILL.md with plugins + --node + --expect sections

### Phase 4: First Plugins

- `chatgpt` — conversation (messages, send, isResponseComplete / save, screenshot), share (extractShareData), common (isLoggedIn)
- `dom` — waitFor(selector), selectAll, extractTable, extractLinks
- `github` — PR files, issue comments, repo metadata

### Phase 5: Human-in-the-Loop

- `browser wait "message"` command
