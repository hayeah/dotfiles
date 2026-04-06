---
name: swiftui
description: SwiftUI development — SPM+XcodeGen project setup, global state tree pattern, and SwiftUITap agent SDK.
globs:
  - "**/*.swift"
  - "**/project.yml"
  - "**/Package.swift"
---

# SwiftUI Developer

## Project Setup (SPM + XcodeGen)

**TLDR**: Push all code into SPM packages. XcodeGen only generates a thin `.xcodeproj` shell for the app target, signing, and assets. `App/Sources/` should be < 100 lines.

```
MyApp/
├── project.yml          ← XcodeGen: app shell only
├── App/Sources/         ← @main + root wiring (tiny)
├── App/Resources/       ← app icon, launch screen
├── Packages/            ← ALL code lives here
│   ├── Core/            ← shared models, utilities
│   ├── Features/        ← multi-target: one per feature
│   └── DesignSystem/    ← shared UI components
└── .gitignore           ← *.xcodeproj, .build/
```

New project setup:

```bash
mkdir MyApp && cd MyApp
# Create Packages/Core/Package.swift, Packages/Features/Package.swift, etc.
# Create project.yml (only declares local packages + app target)
xcodegen generate
echo -e "*.xcodeproj\n.build/" >> .gitignore
```

Key rules:
- **SPM owns all code** — sources, deps, tests, build settings live in `Package.swift`
- **XcodeGen owns the shell** — app target, signing, Info.plist, entitlements, schemes
- **Don't redeclare transitive deps** in `project.yml` — only packages `App/Sources/` directly imports
- **Regenerate rarely** — only when adding/removing packages or changing app-level settings
- **Multi-platform**: set `platforms: [.iOS(.v17), .macOS(.v14)]` in Package.swift, `supportedDestinations: [iOS, macOS]` in project.yml

Full reference: [XcodeGen + SPM-First Guide](guides/xcodegen-spm-first.md)

## Global State Tree

**TLDR**: One `@Observable` class (`AppState`) holds the entire app state. Child domains get their own `@Observable` classes. All views bind to paths in the tree. No scattered stores, no ViewModels per screen.

```swift
#if DEBUG
@SwiftUITap
#endif
@Observable
final class AppState {
    var library: LibraryState = LibraryState()
    var sessions: [ReadingSession] = []

    var __doc__: String {
        """
        AppState — root state tree.
        library.searchQuery (String), library.books ([BookEntry])
        sessions.N.currentChapterIndex (Int)
        Methods: openBook(bookID:chapter:), closeSession(sessionID:)
        """
    }

    func openBook(bookID: String, chapter: Int) -> [String: Any]? { ... }
}
```

Key rules:
- **One tree** — `AppState` → child state classes → plain structs for leaf data
- **Direct set** for single-property writes, **action methods** for multi-step operations
- **`__doc__`** on root class documents the entire tree — no per-class docs
- **`@State`** only for ephemeral view-local state (animation, sheet). App state goes in the tree
- **Explicit type annotations** on all properties — the macro skips unannotated ones
- **No ViewModels** — the state tree IS the view model

File organization:

```
State/
├── AppState.swift           # Root @Observable
├── LibraryState.swift       # Domain subtrees
├── ReadingSession.swift
└── Models/                  # Plain structs (Codable, Identifiable)
```

Full reference: [SwiftUI Global State Guide](guides/swiftui-state.md)

## SwiftUITap (Agent SDK)

**TLDR**: Add `@SwiftUITap` macro to `@Observable` classes. Agents can then get/set properties and call methods over HTTP via `swiftui-tap` CLI. Wrap in `#if DEBUG` for zero production overhead.

```bash
# Start the relay server
swiftui-tap server --port 9876

# Read state
swiftui-tap state get __doc__
swiftui-tap state get .                          # full snapshot
swiftui-tap state get library.searchQuery

# Write state
swiftui-tap state set counter 42
swiftui-tap state set label '"hello"'

# Call methods
swiftui-tap state call addTodo '{"title": "Ship it"}'

# View inspection
swiftui-tap view tree                            # hierarchy dump
swiftui-tap view screenshot                      # full app
swiftui-tap view screenshot ContentView.todoList -o list.png  # cropped
```

App wiring:

```swift
private let sharedAppState = AppState()

@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(sharedAppState)
                .tapInspectable()          // enables view tree + screenshots
                .onAppear {
                    #if DEBUG
                    SwiftUITap.poll(state: sharedAppState, server: "http://localhost:9876")
                    #endif
                }
        }
    }
}
```

Tag views with `.tapID("name")` for targeted screenshots. IDs auto-prefix with source file name.

Key rules:
- **Explicit type annotations** required — macro skips unannotated properties
- **Labeled parameters** required on methods — unlabeled (`_`) params are skipped
- **`#if DEBUG`** around `@SwiftUITap` and `SwiftUITap.poll()` — strips agent code in release
- **Don't call `poll()` in `init()`** — SwiftUI state isn't wired up yet, use `.onAppear`
- **System objects**: dot-prefix paths (`.windows`, `.app`, `.defaults`) access NSObject builtins via KVC

Full reference: [SwiftUITap Guide](guides/swiftui-tap.md)
