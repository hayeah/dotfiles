---
overview: Spec for window.__tap__ — exposes app state, actions, and DOM refs to AI agents for direct manipulation. Stateless, parameterized APIs. Inline __DOC__ string as docstring.
tags:
  - spec
  - design
---

# Web Page Tap API Spec

## The Problem

When an AI agent needs to interact with a webapp, it has to guess at DOM selectors, fumble with querySelector chains, and hope clicks land. The agent already knows the code — just give it direct access.

## Core Idea

Each route exposes app state and actions on `window.__tap__` so the agent can manipulate the app directly — more reliable than clicking buttons or filling inputs. A `__DOC__` string constant in the source file serves as the docstring. The agent sees it when it reads the component — no extra file, no runtime lookup.

## Convention

- **`window.__tap__`** — always this name, one object per route
- **`__DOC__`** — a string constant in the component file. The agent reads it from source, not at runtime. For the agent's context, not the browser.
- **`$` prefix** — DOM elements. `$searchInput`, `$tocButton`, `$scrollArea`
- **Everything else** — state, setters, stores, callbacks. No categories. Just names.
- **Stateless** — prefer APIs that take parameters over ones that depend on prior state. `item(id).details()` not `selectItem(id)` + `getDetails()`. Each call should be self-contained.
- **Per-route** — each page registers on mount, cleans up on unmount

## `__DOC__`

**Must be the very first thing after imports** — before any other code. This placement makes it impossible to miss and obvious that it should be kept in sync when the component changes. Think of it like a Python module docstring: if it's not at the top, nobody maintains it.

````typescript
const __DOC__ = `
# ItemManager

Page for browsing and managing item collections.

## window.__tap__

- collections() — list all collections with id, name, type, itemCount
- collection(id) — get a collection handle
  - .listItems(opts?) — list items, optional { match } filter
  - .addItem(data) — add an item
  - .remove() — delete the collection
- navigate(path) — push a route
- route() — current pathname

## Usage

List all collections:

    __tap__.collections()

Search items in a collection:

    await __tap__.collection("abc").listItems({ match: "query" })

Navigate to an item:

    __tap__.navigate("/items/123")
`;
````

The agent reads the source file, sees `__DOC__`, knows what's on `__tap__`. One file, zero extra reads.

## Example: Stateless API with Handles

The key pattern: return **handle objects** parameterized by ID, so the agent never needs to "select" something first.

```typescript
interface CollectionHandle {
  id: string;
  name: string;
  type: string;
  listItems(opts?: { match?: string }): Promise<...>;
  openItem(itemId: string): Promise<void>;
  sync(): Promise<{ itemCount: number }>;
  remove(): Promise<void>;
}

interface AppTapAPI {
  collections(): { id: string; name: string; type: string; itemCount: number }[];
  collection(id: string): CollectionHandle;
  addCollection(name?: string): Promise<CollectionHandle>;
  navigate(path: string): void;
  route(): string;
}
```

Notice: `collection(id).listItems()` — not `selectCollection(id)` then `listItems()`. Every call is self-contained. The agent never needs to track which collection is "active".

## Browser Tool Usage

```bash
# List collections
browser eval -s a3f2 '__tap__.collections()'

# Search items in a specific collection
browser eval -s a3f2 'await __tap__.collection("abc").listItems({ match: "alice" })'

# Open an item
browser eval -s a3f2 'await __tap__.collection("abc").openItem("item-123")'

# Navigate
browser eval -s a3f2 '__tap__.navigate("/settings")'

# Screenshot after navigating
browser screenshot --open http://localhost:5173 \
  --steps '
- eval: __tap__.navigate("/items")
  wait: document.querySelector(".item-list")
'
```

## Summary

- App state and actions on `window.__tap__` — agent manipulates state directly, not through UI
- **Stateless handles** — `collection(id).listItems()`, not `selectCollection()` + `listItems()`
- `__DOC__` string in the source file — agent reads it from code, not at runtime
- `$` prefix for DOM elements, everything else is state/callbacks
- The agent reads the component, sees `__DOC__`, knows how to drive the page
