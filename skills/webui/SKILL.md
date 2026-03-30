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

## Dev Workflow

When working on a page, use the tap API + screenshots to verify different states:

```bash
# Start dev server on an explicit port (see Port Usage below)
vp dev --port 5173

# Open a session
browser open http://localhost:5173    # → session key a3f2

# Manipulate state via tap API, screenshot each state
browser eval -s a3f2 '__tap__.library.searchQuery = "alice"'
browser screenshot -s a3f2 -o "$(tmpfile search.png)"

browser eval -s a3f2 '__tap__.openBook("alice-123", 5)'
browser screenshot -s a3f2 -o "$(tmpfile reader.png)"

# Or use multi-step screenshots for a quick sweep
browser screenshot --open http://localhost:5173 \
  -o "$(tmpfile states.png)" \
  --steps '
- wait: __tap__
- eval: __tap__.library.searchQuery = "alice"
  wait: document.querySelector(".book-list")
- eval: __tap__.openBook("alice-123", 5)
  wait: document.querySelector(".reader")
'
```

Read the `__DOC__` in the root store to see what's available on `__tap__`, then drive the app through its states programmatically. Screenshot to confirm each state looks right.

## Port Usage

Always start the dev server with an explicit port. Vite auto-finds an unused port when the default is taken, which causes the agent to lose track of the URL.

Find a free port (checks both `127.0.0.1` and `0.0.0.0`):

```bash
python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); s2=socket.socket(); s2.bind(('0.0.0.0',p)); s2.close(); print(p)"
```

Then start with that port:

```bash
vp dev --port 5173
```

## File Conventions

- **PascalCase** for React components and files (`BookLibrary.tsx`)
- **camelCase** with `use` prefix for hooks (`useReadingProgress.ts`)

Group files by page (roughly mapping to routes), not by type (`hooks/`, `utils/`). Keep bespoke helpers and subcomponents together with the page they belong to.

```
pages/
  reader/
    Reader.tsx              # entry component
    Reader.test.tsx
    ReaderToolbar.tsx        # subcomponent
    ReaderChapterNav.tsx     # subcomponent
  library/
    Library.tsx
    Library.test.tsx
    LibrarySearch.tsx
    LibraryShelf.tsx
State/
  AppStore.ts
  LibraryStore.ts
  ReadingSession.ts
  StoreContext.ts
  Models/
    BookEntry.ts
```

## Coding Conventions

- For complex features, avoid bags of loose functions.
  - Group related methods in a class.
  - Prefer class properties over passing shared state through parameters.
- Name getters as nouns, not `get*` — e.g. `user()` not `getUser()`.

### Classes

- Use `constructor(public foo: string, public bar: number)` to declare and assign instance properties.
- Prefer composition and injection over constructing dependencies inside the constructor.
- For async initialization, use a static factory method that injects the awaited value into a normal constructor. Avoids needing an `init` instance method.

```typescript
class Reader {
  // Static factory for async setup
  static async create(bookId: string) {
    const metadata = await fetchMetadata(bookId);
    return new Reader(bookId, metadata);
  }

  constructor(
    public bookId: string,
    public metadata: BookMetadata,
  ) {}
}
```

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

For scripts longer than ~10 lines, write to a temp file:

```bash
# Get a path
tmpfile scrape.js
# => $MDNOTES_ROOT/2026-03-30/tmp/143052.283-scrape.js

# Write your script to that path (use the Write tool)

# Run it
browser eval -s a3f2 $MDNOTES_ROOT/2026-03-30/tmp/143052.283-scrape.js
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
- **`window.__tap__`** — always this name, one object per app
- **`__DOC__`** — string constant, first thing after imports (like a Python module docstring)
- **`$` prefix** — DOM elements (`$searchInput`, `$scrollArea`)
- **Register once** — set up on app init
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
