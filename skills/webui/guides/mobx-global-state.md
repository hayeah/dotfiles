---
overview: Guide for MobX global state tree in React apps — single observable root, all components bind to paths within the tree, agent-drivable via window.__tap__.
tags:
  - guide
  - design
---

# MobX Global State Tree — Guide

## Overview

Use a **single MobX observable tree** rooted in one store object. All React components observe paths within this tree via `mobx-react-lite`. The root store is exposed on `window.__tap__` so agents can read, write, and call methods directly.

## Why This Pattern

- **One source of truth** — one root store, child stores organized by domain
- **Agent-drivable** — every property is reachable by dot-path (e.g., `__tap__.library.searchQuery`), every method callable
- **Easy to stub** — set any state for tests or screenshots without mocks
- **Transparent data flow** — each component declares which store path it observes
- **MobX auto-tracking** — fine-grained reactivity, no manual dependency arrays

---

## State Tree Structure

### Root Store

One observable object. This is the entire app's state:

```typescript
// State/AppStore.ts
import { makeAutoObservable } from "mobx";
import { LibraryStore } from "./LibraryStore";
import { ReadingSession } from "./ReadingSession";

const __DOC__ = `
# AppStore — window.__tap__

Single source of truth for the entire app. All components observe
paths within this tree. All state is reachable from here.

## State Tree

library (LibraryStore) — book library and browsing
  .searchQuery (string)         — set to filter the book list, "" = no filter
  .books (BookEntry[])          — all entries {id, title, author, filename}
  .activeLibraryID (string?)    — selected library folder, null = show all
  .filteredBooks                — computed, filtered by searchQuery

sessions (ReadingSession[]) — open reading sessions, one per book
  sessions[N] (ReadingSession):
    .bookID (string)                  — ID of the open book
    .currentChapterIndex (number)     — zero-based chapter index
    .scrollFraction (number)          — scroll position within chapter, 0.0–1.0
    .isChapterSwitcherVisible (bool)  — TOC overlay
    .isBottomBarVisible (bool)        — bottom navigation bar
    .nextChapter()                    — advance one chapter
    .previousChapter()               — go back one chapter (clamped to 0)

## Methods

openBook(bookID, chapter?) → { sessionIndex }
  Opens a book. Creates a new ReadingSession, appends to sessions.

closeSession(sessionID)
  Removes the session with the given ID.

## Common Workflows

Open a book and jump to chapter 5:
  __tap__.openBook("alice-123", 5)

Search the library:
  __tap__.library.searchQuery = "alice"

Clear search:
  __tap__.library.searchQuery = ""

Navigate an open book:
  __tap__.sessions[0].currentChapterIndex = 8

Scroll to middle of current chapter:
  __tap__.sessions[0].scrollFraction = 0.5

Show the chapter switcher overlay:
  __tap__.sessions[0].isChapterSwitcherVisible = true
`;

export class AppStore {
  library = new LibraryStore();
  sessions: ReadingSession[] = [];

  constructor() {
    makeAutoObservable(this);
  }

  get openBookIDs(): Set<string> {
    return new Set(this.sessions.map((s) => s.bookID));
  }

  openBook(bookID: string, chapter = 0) {
    const session = new ReadingSession(bookID, chapter);
    this.sessions.push(session);
    return { sessionIndex: this.sessions.length - 1 };
  }

  closeSession(sessionID: string) {
    this.sessions = this.sessions.filter((s) => s.id !== sessionID);
  }
}
```

### Child Store Classes

Each logical domain gets its own MobX class:

```typescript
// State/LibraryStore.ts
import { makeAutoObservable } from "mobx";
import type { BookEntry } from "./Models/BookEntry";

export class LibraryStore {
  searchQuery = "";
  activeLibraryID: string | null = null;
  books: BookEntry[] = [];

  constructor() {
    makeAutoObservable(this);
  }

  get filteredBooks(): BookEntry[] {
    if (!this.searchQuery) return this.books;
    const q = this.searchQuery.toLowerCase();
    return this.books.filter(
      (b) =>
        b.title.toLowerCase().includes(q) ||
        b.author?.toLowerCase().includes(q),
    );
  }
}

// State/ReadingSession.ts
import { makeAutoObservable } from "mobx";
import { nanoid } from "nanoid";

export class ReadingSession {
  id = nanoid();
  bookID: string;
  currentChapterIndex: number;
  scrollFraction = 0;
  isChapterSwitcherVisible = false;
  isBottomBarVisible = true;

  constructor(bookID: string, chapter = 0) {
    this.bookID = bookID;
    this.currentChapterIndex = chapter;
    makeAutoObservable(this);
  }

  nextChapter() {
    this.currentChapterIndex += 1;
  }

  previousChapter() {
    this.currentChapterIndex = Math.max(0, this.currentChapterIndex - 1);
  }
}
```

### Data Models (plain types)

Leaf data that doesn't need reactivity — plain interfaces or types:

```typescript
// State/Models/BookEntry.ts
export interface BookEntry {
  id: string;
  title: string;
  author?: string;
  filename: string;
}

// State/Models/Chapter.ts
export interface Chapter {
  id: string;
  index: number;
  title: string;
}
```

**Rule of thumb**: if an agent or component needs to observe/mutate properties on it, make it a MobX class with `makeAutoObservable`. If it's just data passed around, use a plain interface.

---

## Rules

### `__DOC__` on the Root Store

One `__DOC__` on the root store file covers the **entire** state tree — every property, method, child store's fields, with workflows and notes. The agent reads one string and knows how to interact with the whole app.

No per-class `__DOC__`. Child store classes don't need their own — the root doc covers them by path.

### Direct Set vs Action Methods

**Direct set** — for single-property writes with no side effects:

```tsx
// Component
<button onClick={() => { session.isChapterSwitcherVisible = true; }}>
  Show Chapters
</button>

// Agent
// __tap__.sessions[0].isChapterSwitcherVisible = true
```

This covers UI toggles, text fields, numeric values. No method wrapper needed — `setSearchQuery(q)` for a single property write is just ceremony.

**Action method** — when the operation touches multiple properties, has invariants, or produces a result:

```typescript
openBook(bookID: string, chapter = 0) {
  const session = new ReadingSession(bookID, chapter);
  this.sessions.push(session);
  return { sessionIndex: this.sessions.length - 1 };
}
```

**The rule**: if setting a property has side effects or touches multiple properties, make it a method. If it's a single-property write, just set it directly.

### Component Binding

Components observe store paths via `observer()` from `mobx-react-lite`:

```tsx
import { observer } from "mobx-react-lite";

const LibraryView = observer(({ store }: { store: AppStore }) => {
  return (
    <div>
      <input
        value={store.library.searchQuery}
        onChange={(e) => { store.library.searchQuery = e.target.value; }}
      />
      <ul>
        {store.library.filteredBooks.map((book) => (
          <BookRow key={book.id} book={book} />
        ))}
      </ul>
    </div>
  );
});

const ReadingView = observer(({ session }: { session: ReadingSession }) => {
  return <div>{session.currentChapterIndex}</div>;
});
```

Pass the store via React context from the root:

```tsx
// StoreContext.ts
import { createContext, useContext } from "react";
import type { AppStore } from "./State/AppStore";

const StoreContext = createContext<AppStore>(null!);
export const StoreProvider = StoreContext.Provider;
export const useStore = () => useContext(StoreContext);

// main.tsx
const appStore = new AppStore();

// Register tap API
window.__tap__ = appStore;

createRoot(document.getElementById("root")!).render(
  <StoreProvider value={appStore}>
    <App />
  </StoreProvider>,
);
```

### State Organization

```
AppStore                          ← root, one per app
├── library: LibraryStore         ← domain subtree
│   ├── searchQuery: string
│   ├── books: BookEntry[]
│   ├── activeLibraryID: string?
│   └── filteredBooks (computed)
├── sessions: ReadingSession[]    ← array of domain objects
│   ├── [0]: ReadingSession
│   │   ├── currentChapterIndex: number
│   │   ├── scrollFraction: number
│   │   └── isChapterSwitcherVisible: boolean
│   └── [1]: ReadingSession
│       └── ...
└── router: RouterStore           ← navigation state (if needed)
    └── currentRoute: string
```

Every node in this tree is reachable from `window.__tap__`:
- `__tap__.library.searchQuery`
- `__tap__.sessions[0].currentChapterIndex`
- `__tap__.sessions[1].isChapterSwitcherVisible`

---

## Anti-Patterns

- **State in components** — `useState` is fine for ephemeral view-local state (animation, hover). Anything an agent might care about goes in the tree.
- **Private state** — don't hide state behind private fields. The tree should be fully inspectable from `__tap__`.
- **Wrapper setters** — don't write `setSearchQuery(q)` for single-property writes. Just set the property directly.

---

## File Organization

```
State/
├── AppStore.ts              # Root store, top-level actions, __DOC__
├── LibraryStore.ts          # Library domain
├── ReadingSession.ts        # Per-session domain
├── RouterStore.ts           # Navigation (if needed)
├── StoreContext.ts          # React context + useStore hook
└── Models/                  # Plain interfaces
    ├── BookEntry.ts
    ├── Chapter.ts
    └── TOCItem.ts
```

State classes go in `State/`. Plain data models go in `State/Models/`. Components never define store classes — they only observe them.

---

## Tap API Registration

The simplest approach: expose the root store directly as `window.__tap__`.

```typescript
// main.tsx
const appStore = new AppStore();
window.__tap__ = appStore;
```

Since MobX observables are plain objects with getters/setters, the agent can read and write properties directly:

```bash
# Read
browser eval -s a3f2 '__tap__.library.searchQuery'

# Write (triggers MobX reactivity → UI updates)
browser eval -s a3f2 '__tap__.library.searchQuery = "alice"'

# Call methods
browser eval -s a3f2 '__tap__.openBook("alice-123", 5)'

# Screenshot after state change
browser screenshot --open http://localhost:5173 \
  --steps '
- eval: __tap__.library.searchQuery = "alice"
  wait: document.querySelector(".book-list")
'
```

MobX makes this seamless — setting a property on the store triggers the same reactive update path as a user typing in an input.
