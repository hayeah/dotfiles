---
name: webui
description: Web UI development — Vite+ toolchain setup and browser-based E2E testing workflow.
globs:
  - "**/*.tsx"
  - "**/*.jsx"
  - vite.config.*
  - package.json
---

# Web UI Development

## Setup & Tooling

**TLDR**: Use Vite+ (`vp`) as the unified toolchain — it replaces Vite, Vitest, ESLint, Prettier in one CLI.

```bash
vp create       # scaffold new project
vp install      # install dependencies
vp dev          # dev server
vp check        # format + lint + type-check in one pass
vp test         # run tests
vp build        # production build
```

Everything lives in a single `vite.config.ts` — no separate vitest/eslint/prettier configs. Import from `'vite-plus'` and `'vite-plus/test'` instead of `'vite'`/`'vitest'`.

Full reference: [Vite+ Guide](guides/viteplus.md)

## Browser Testing

**TLDR**: Use the `browser` skill for E2E testing — screenshot, eval JS, inspect pages. Prefer `--open` one-shot mode for quick checks.

### Screenshot with Different Devices

```bash
# Desktop (default)
browser screenshot --open http://localhost:5173

# Mobile device emulation
browser screenshot --open '{"device":"iPhone 15 Pro","url":"http://localhost:5173"}'

# Custom viewport with retina DPR
browser screenshot --open '{"url":"http://localhost:5173","viewport":"1280x800@2"}'

# Save to specific path
browser screenshot --open http://localhost:5173 -o "$(tmpfile desktop.png)"
```

Device names resolve against Puppeteer's KnownDevices (case-insensitive prefix match).

### Eval JavaScript

Run JS in the browser context — pass inline code or a file path:

```bash
browser eval --open http://localhost:5173 'document.title'
browser eval -s a3f2 'document.querySelectorAll("button").length'
browser eval -s a3f2 myscript.js
```

For scripts longer than ~10 lines, write to a temp file first:

```bash
# Write script via Write tool, then:
browser eval -s a3f2 "$(tmpfile scrape.js)"
```

### One-Shot Mode (`--open`)

Opens a window, runs the command, closes the window. No session management needed:

```bash
browser screenshot --open https://example.com
browser content --open https://example.com
browser eval --open https://example.com 'document.title'
browser network --open https://example.com --type xhr
```

Context spec formats:
- **Bare URL**: `https://example.com` — desktop defaults
- **JSON**: `'{"device":"iPhone 15 Pro","url":"https://example.com"}'` — device emulation
- **TOML file**: `mobile.toml` — reusable device profiles

### Persistent Sessions

For multi-step workflows, use persistent sessions:

```bash
# Open (run in background — process lifetime = session lifetime)
browser open http://localhost:5173    # prints session key, e.g. a3f2

# Use
browser screenshot -s a3f2
browser eval -s a3f2 'document.title'
browser nav -s a3f2 http://localhost:5173/other
# Close
browser close -s a3f2
```

### Multi-Step Screenshots

Capture multiple states from a single page load:

```bash
browser screenshot --open http://localhost:5173 \
  -o "$(tmpfile flow.png)" \
  --steps '
- wait: document.querySelector(".loaded")
- eval: document.querySelector("button").click()
  wait: document.querySelector(".modal")
'
```

Output files get an index: `flow.1.png`, `flow.2.png`, etc.

### Efficiency Tips

- Batch DOM interactions in a single `eval` IIFE
- Use `browser content` for readable text extraction (uses Readability)
- Use `browser network --type xhr` to discover API endpoints

Full reference: [browser skill](~/github.com/hayeah/dotfiles/skills/browser/SKILL.md)

## MobX Global State

**TLDR**: One MobX observable tree rooted in a single `AppStore`, with child stores organized by domain. All components observe paths in the tree via `observer()`.

```typescript
// State/AppStore.ts
class AppStore {
  library = new LibraryStore();
  sessions: ReadingSession[] = [];
  constructor() { makeAutoObservable(this); }

  openBook(bookID: string, chapter = 0) { /* ... */ }
}

// main.tsx
const appStore = new AppStore();
window.__tap__ = appStore;
```

Key rules:
- **One tree** — `AppStore` → child stores → plain data. No scattered contexts.
- **Direct set** for single-property writes (`store.searchQuery = "alice"`), **action methods** when touching multiple properties or returning results
- **`__DOC__`** on the root store file covers the entire tree — one string, all paths and methods
- **`useState` only for ephemeral** view-local state (animation, hover). Everything else goes in the tree.
- **No wrapper setters** — don't write `setSearchQuery(q)` for a single property. Just set it.

Full reference: [MobX Global State Guide](guides/mobx-global-state.md)

## Web Page Tap API

**TLDR**: Expose app state and actions on `window.__tap__` so the agent can manipulate the app directly — more reliable than clicking buttons or filling inputs. Prefer stateless APIs: `tabContent(index)` not `switchToTab(index)` + `tabContent()`. Use `__DOC__` as a source-level docstring. `$` prefix for DOM refs, everything else is state/callbacks.

```tsx
const __DOC__ = `
# MyPage — window.__tap__
- store.searchQuery (string) — current filter
- store.sheetOpen (boolean) — sheet visibility
- setActiveItem(id) — select item and close sheet
- $searchInput — the search <input>
`;

const store = observable({ searchQuery: '', sheetOpen: false });

useEffect(() => {
  window.__tap__ = {
    store,
    setActiveItem(id: string) { /* ... */ },
    get $searchInput() { return searchRef.current; },
  };
  return () => { window.__tap__ = null; };
}, []);
```

Key conventions:
- **`window.__tap__`** — always this name, one object per route
- **`__DOC__`** — string constant, first thing after imports (like a Python module docstring)
- **`$` prefix** — DOM elements (`$searchInput`, `$scrollArea`)
- **Per-route** — register on mount, clean up on unmount
- Works with MobX (cleanest), React useState, or Zustand

Agent drives the page via `browser eval`:

```bash
browser eval -s a3f2 '__tap__.store.sheetOpen = true'
browser eval -s a3f2 '__tap__.$searchInput.focus()'

# Screenshot after state change
browser screenshot --open http://localhost:5173 \
  --steps '
- eval: __tap__.store.sheetOpen = true
  wait: document.querySelector(".sheet")
'
```

Full reference: [Web Tap API Guide](guides/web-tap-api.md)
