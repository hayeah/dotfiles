---
source: https://github.com/hayeah/SwiftUITap/blob/master/docs/swiftui-state-skill.md
---

# SwiftUI Global State Tree — SKILL Guide

## Overview

This skill guides you to write SwiftUI apps with a **single global state tree** rooted in one `@Observable` object. All views bind to paths within this tree. State classes use the `@SwiftUITap` macro to generate dispatch code so that agents can read, write, and call methods programmatically via string paths.

## Why This Pattern

- **One source of truth** — no scattered stores, no DI containers, no ambient singletons
- **Agent-drivable** — every property is addressable by dot-path string (e.g., `library.searchQuery`), every method callable by name
- **Easy to stub** — set any state for previews, tests, or screenshots without mocks
- **Transparent data flow** — each view declares which path in the tree it binds to
- **Zero runtime cost in production** — wrap `@SwiftUITap` in `#if DEBUG`, release builds are plain `@Observable`

---

## State Tree Structure

### Root State

One `@Observable` class. This is the entire app's state:

```swift
import SwiftUITap

#if DEBUG
@SwiftUITap
#endif
@Observable
final class AppState {
    var __doc__: String {
        """
        AppState — EPUB Reader state tree.

        Single source of truth for the entire app. All views bind to
        paths within this tree. All state is reachable from here.

        ## State Tree

        library (LibraryState) — book library and browsing
          .searchQuery (String)         — set to filter the book list, "" = no filter
          .books ([BookEntry])          — all BookEntry objects {id, title, author, filename}
          .activeLibraryID (String?)    — selected library folder, nil = show all

        sessions ([ReadingSession]) — open reading sessions, one per book
          sessions.N (ReadingSession):
            .bookID (String)                  — ID of the open book
            .currentChapterIndex (Int)        — zero-based chapter index
            .scrollFraction (Double)          — scroll position within chapter, 0.0–1.0
            .isChapterSwitcherVisible (Bool)  — TOC overlay
            .isBottomBarVisible (Bool)        — bottom navigation bar
            .nextChapter()                    — advance one chapter
            .previousChapter()                — go back one chapter (clamped to 0)

        ## Methods

        openBook(bookID: String, chapter: Int) → {"sessionIndex": N}
          Opens a book. Creates a new ReadingSession and appends it to
          `sessions`. Returns the index of the new session.

        closeSession(sessionID: String)
          Removes the session with the given UUID string from `sessions`.

        ## Common Workflows

        Open a book and jump to chapter 5:
          call openBook {"bookID": "alice-123", "chapter": 5}

        Search the library:
          set library.searchQuery "alice"
          get library  → includes filtered books in response

        Clear search:
          set library.searchQuery ""

        Inspect all open sessions:
          get sessions  → array of ReadingSession snapshots

        Navigate an open book:
          set sessions.0.currentChapterIndex 8
          set sessions.0.scrollFraction 0.0

        Scroll to middle of current chapter:
          set sessions.0.scrollFraction 0.5

        Show the chapter switcher overlay:
          set sessions.0.isChapterSwitcherVisible true

        Hide bottom bar (full-screen reading):
          set sessions.0.isBottomBarVisible false

        ## Notes

        - Changing currentChapterIndex resets scrollFraction to 0.
          The view auto-loads chapter content when the index changes.
        - library.books is read-only from the agent's perspective —
          books come from scanning library folders. Use openBook() to
          read one.
        - Direct property sets are fine for simple values (toggles,
          text, numbers). Use methods for multi-step operations.
        """
    }

    var library: LibraryState = LibraryState()
    var sessions: [ReadingSession] = []

    // Derived — computed, not stored
    var openBookIDs: Set<String> { Set(sessions.map { $0.bookID }) }

    // Actions
    func openBook(bookID: String, chapter: Int) -> [String: Any]? {
        let session = ReadingSession(bookID: bookID, chapter: chapter)
        sessions.append(session)
        return ["sessionIndex": sessions.count - 1]
    }

    func closeSession(sessionID: String) {
        sessions.removeAll { $0.id.uuidString == sessionID }
    }
}
```

### Child State Classes

Each logical domain gets its own `@Observable` class with `@SwiftUITap`:

```swift
#if DEBUG
@SwiftUITap
#endif
@Observable
final class LibraryState {
    var searchQuery: String = ""
    var activeLibraryID: String? = nil
    var books: [BookEntry] = []

    // Derived — computed, read-only to agents
    var filteredBooks: [BookEntry] {
        guard !searchQuery.isEmpty else { return books }
        return books.filter { $0.matches(searchQuery) }
    }
}

#if DEBUG
@SwiftUITap
#endif
@Observable
final class ReadingSession: Identifiable {
    let id = UUID()

    var bookID: String = ""
    var currentChapterIndex: Int = 0
    var scrollFraction: Double = 0.0
    var isChapterSwitcherVisible: Bool = false
    var isBottomBarVisible: Bool = true

    init(bookID: String, chapter: Int) {
        self.bookID = bookID
        self.currentChapterIndex = chapter
    }

    // Actions
    func nextChapter() { currentChapterIndex += 1 }
    func previousChapter() { currentChapterIndex = max(0, currentChapterIndex - 1) }
}
```

### Data Models (plain structs)

Leaf data — things that don't need to be individually addressable by agents — are plain structs:

```swift
struct BookEntry: Identifiable, Codable {
    let id: String
    let title: String
    let author: String
    let filename: String
}

struct Chapter: Identifiable {
    let id: String
    let index: Int
    let title: String
}
```

**Rule of thumb**: if an agent needs to get/set properties on it by path, make it an `@Observable` class with `@SwiftUITap`. If it's just data passed around, use a struct.

---

## Rules

### Property Declarations

The `@SwiftUITap` macro needs **explicit type annotations** on every property it should expose:

```swift
// EXPOSED — explicit type annotation
var counter: Int = 0
var label: String = "hello"
var darkMode: Bool = false
var name: String? = nil
var todos: [TodoItem] = []
var settings: SettingsState = SettingsState()

// SKIPPED — no type annotation (invisible to agent)
var settings = SettingsState()
var count = 0

// SKIPPED — complex generics
var lookup: [String: TodoItem] = [:]
var callback: (() -> Void)? = nil
```

| Type annotation | Get | Set | Notes |
|---|---|---|---|
| `String`, `Int`, `Double`, `Bool` | yes | yes | Direct JSON mapping |
| `String?`, `Int?`, etc. | yes | yes | nil ↔ JSON null |
| `[T]` | yes | index traversal | `todos.0.title` |
| Any other class identifier | yes | delegate to child | Runtime `as? TapDispatchable` check |
| `let` / computed | yes | no | Read-only |
| No type annotation | skipped | skipped | Invisible to agent |

### `__doc__` on the Root State Class

One `__doc__` on `AppState` that covers the **entire** state tree — every property, every method, every child class's fields, with workflows and notes. The agent reads one string and knows how to interact with the whole app.

No per-class `__doc__`. Child state classes don't need their own — the root doc covers them by path.

### Direct Set vs Action Methods

Views (and agents) can mutate state in two ways: set a property directly, or call a method. Use whichever fits:

**Direct set** — for single-property writes with no side effects:

```swift
// View
Button("Show Chapters") {
    session.isChapterSwitcherVisible = true
}

// Agent
// set sessions.0.isChapterSwitcherVisible true
```

This covers UI toggles (`isBottomBarVisible`, `isChapterSwitcherVisible`), text fields (`searchQuery`), numeric values (`currentChapterIndex`, `scrollFraction`). No method wrapper needed — adding `setSearchQuery(_ q: String)` for a single property write is just ceremony.

**Action method** — when the operation touches multiple properties, has invariants, or produces a result:

```swift
func openBook(bookID: String, chapter: Int) -> [String: Any]? {
    let session = ReadingSession(bookID: bookID, chapter: chapter)
    sessions.append(session)
    return ["sessionIndex": sessions.count - 1]
}

func closeSession(sessionID: String) {
    sessions.removeAll { $0.id.uuidString == sessionID }
}
```

**The rule**: if setting a property has side effects or touches multiple properties, make it a method. If it's a single-property write, just set it directly.

Both are equally testable — the state tree is a plain object, no mocks needed:

```swift
func testSearchFilters() {
    let state = LibraryState()
    state.books = [BookEntry(title: "Alice"), BookEntry(title: "Moby Dick")]
    state.searchQuery = "alice"
    XCTAssertEqual(state.filteredBooks.count, 1)
}

func testOpenBook() {
    let state = AppState()
    let result = state.openBook(bookID: "abc", chapter: 3)
    XCTAssertEqual(state.sessions.count, 1)
    XCTAssertEqual(result?["sessionIndex"] as? Int, 0)
}
```

### Agent-Callable Methods

Methods the macro exposes must have **labeled parameters**:

```swift
// EXPOSED — labeled params, supported types
func addTodo(title: String) -> [String: Any]? { ... }
func toggleTodo(index: Int) { ... }
func reset() { ... }

// EXPOSED — Codable params and returns
func moveTo(point: Point) -> MoveResult { ... }

// SKIPPED — unlabeled param
func process(_ items: [TodoItem]) { ... }

// SKIPPED — private
private func internalHelper() { ... }
```

**Parameter types:**
- `String`, `Int`, `Double`, `Bool` → direct JSON cast
- Any other type → `Decodable` (decoded from JSON)

**Return types:**
- `Void` → null
- Primitives, `[String: Any]?` → passed through
- Any other type → `Encodable` (encoded to JSON)

### View Binding

Views receive a reference to the state subtree they need:

```swift
struct ReadingView: View {
    let session: ReadingSession

    var body: some View {
        Text(session.chapterTitle)
    }
}

struct LibraryView: View {
    @Environment(AppState.self) var appState

    var body: some View {
        List(appState.library.filteredBooks) { book in
            BookRow(book: book)
        }
    }
}
```

Pass state via SwiftUI environment from the root:

```swift
private let sharedAppState = AppState()

@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(sharedAppState)
                .tapInspectable()
                .onAppear {
                    #if DEBUG
                    SwiftUITap.poll(state: sharedAppState, server: "http://localhost:9876")
                    #endif
                }
        }
    }
}
```

### View Tagging

Tag views with `.tapID()` so agents can dump the view tree and take targeted screenshots:

```swift
struct ContentView: View {
    var body: some View {
        VStack {
            TextField("Search", text: $state.query)
                .tapID("searchField")
            List { ... }
                .tapID("todoList")
            Button("Add") { ... }
                .tapID("addButton")
        }
        .tapID("root")
    }
}
```

IDs are auto-prefixed with the source file name: `ContentView.root`, `ContentView.todoList`, etc.

### State Organization

```
AppState                          ← root, one per app
├── library: LibraryState         ← domain subtree
│   ├── searchQuery: String
│   ├── books: [BookEntry]
│   └── activeLibraryID: String?
├── sessions: [ReadingSession]    ← array of domain objects
│   ├── [0]: ReadingSession
│   │   ├── currentChapterIndex: Int
│   │   ├── scrollFraction: Double
│   │   └── isChapterSwitcherVisible: Bool
│   └── [1]: ReadingSession
│       └── ...
└── router: RouterState           ← navigation state (if needed)
    └── currentRoute: String
```

Every node in this tree is addressable by dot-path:
- `library.searchQuery`
- `sessions.0.currentChapterIndex`
- `sessions.1.isChapterSwitcherVisible`

---

## Anti-Patterns

- **Scattered ObservableObjects** — don't use multiple `@StateObject` / `@EnvironmentObject` scattered across views. One tree.
- **ViewModels per screen** — no `LibraryViewModel`, `ReaderViewModel`. The state tree IS the view model.
- **State in views** — `@State` is fine for ephemeral view-local state (animation, sheet presentation). Anything an agent might care about goes in the tree.
- **Protocols on state classes** — no `TapExposable` or similar. Just `@SwiftUITap` macro on `@Observable` classes.
- **Registries for methods** — no method registry. The macro generates dispatch from your class declaration.
- **Private state** — don't hide state behind private access. The tree should be fully inspectable. If a property exists, it's readable.

---

## File Organization

```
State/
├── AppState.swift           # Root @Observable, top-level actions
├── LibraryState.swift       # Library domain
├── ReadingSession.swift     # Per-session domain
├── RouterState.swift        # Navigation (if needed)
└── Models/                  # Plain structs (Codable, Identifiable)
    ├── BookEntry.swift
    ├── Chapter.swift
    └── TOCItem.swift
```

State classes go in `State/`. Plain data models go in `State/Models/`. Views never define state classes — they only receive references.
