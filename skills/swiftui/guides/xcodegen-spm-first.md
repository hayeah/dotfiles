---
source: /Users/me/Dropbox/notes/2026-03-30/xcodegen-spm-first_claude.md
---

# XcodeGen + SPM-First: Minimal .xcodeproj

> **Prerequisite:** see [Swift Package Manager Guide](swift-package-manager-guide_claude.md) for full SPM reference (Package.swift format, targets, dependencies, resources, plugins, build settings, CLI).

## The Core Idea

SPM handles: source files, dependencies, targets, test targets, multi-platform support, resources, build plugins, and build settings. An `.xcodeproj` is only needed for things SPM can't do:

- **App target** — SPM can't produce `.app` bundles
- **Signing & capabilities** — code signing, entitlements, provisioning
- **App-level assets** — app icon, launch screen
- **Info.plist** — app-specific keys (permissions, orientations, etc.)
- **Schemes** — custom run/test/archive configurations
- **UI tests** — Xcode UI testing bundles

Everything else belongs in SPM packages. XcodeGen generates the minimal `.xcodeproj` shell.

## Why SPM-First Over Pure XcodeGen

| Concern | Pure XcodeGen | SPM-First |
|---|---|---|
| Dependency resolution | Manual in `project.yml` | Native SPM — transitive deps handled automatically |
| Build caching | Xcode incremental | SPM module cache + Xcode incremental |
| Testing without Xcode | No | `swift test` per package |
| Config surface area | Every target in YAML | Only app shell in YAML |
| Code reuse | Copy or framework targets | Import as package anywhere |
| CI parallelism | One xcodebuild | `swift test` per package + xcodebuild for app |

## Project Layout

```
MyApp/
├── project.yml                    ← XcodeGen: thin app shell only
├── .gitignore                     ← *.xcodeproj, .build/
├── App/                           ← minimal — just the entry point
│   ├── Sources/
│   │   └── MyApp.swift            ← @main, imports feature packages
│   ├── Resources/
│   │   ├── Assets.xcassets        ← app icon, accent color
│   │   └── LaunchScreen.storyboard
│   ├── Tests/                     ← app-level integration tests only
│   └── UITests/                   ← UI tests
├── Packages/                      ← ALL code lives here
│   ├── Core/                      ← shared models, utilities
│   │   └── Package.swift
│   ├── Networking/                ← API client, depends on Core
│   │   └── Package.swift
│   ├── DesignSystem/              ← shared UI components
│   │   └── Package.swift
│   └── Features/                  ← multi-target: Home, Profile, Settings
│       └── Package.swift
└── scripts/                       ← CI, build helpers
```

Rule of thumb: `App/Sources/` should be < 100 lines. Just `@main`, a root coordinator/router, and dependency injection wiring.

## Step-by-Step Setup

### Step 1: Design Your Package Graph

Think in layers. Each package declares its own dependencies via `Package.swift` — XcodeGen never sees internal wiring.

```
Features  →  Networking  →  Core
    ↓            ↓
DesignSystem    Core
```

Keep the dependency graph acyclic. Lower layers (Core) should have zero or minimal external dependencies.

### Step 2: Create Packages

**`Packages/Core/Package.swift`:**

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Core",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "Core", targets: ["Core"]),
    ],
    targets: [
        .target(
            name: "Core",
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),
        .testTarget(name: "CoreTests", dependencies: ["Core"]),
    ]
)
```

**`Packages/Networking/Package.swift`:**

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Networking",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "Networking", targets: ["Networking"]),
    ],
    dependencies: [
        .package(url: "https://github.com/Alamofire/Alamofire", from: "5.9.0"),
        .package(path: "../Core"),
    ],
    targets: [
        .target(
            name: "Networking",
            dependencies: ["Core", "Alamofire"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),
        .testTarget(name: "NetworkingTests", dependencies: ["Networking"]),
    ]
)
```

**`Packages/Features/Package.swift`** — multi-target for all feature modules:

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Features",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "Home", targets: ["Home"]),
        .library(name: "Profile", targets: ["Profile"]),
        .library(name: "Settings", targets: ["Settings"]),
    ],
    dependencies: [
        .package(path: "../Core"),
        .package(path: "../Networking"),
        .package(path: "../DesignSystem"),
    ],
    targets: [
        .target(name: "Home", dependencies: ["Core", "Networking", "DesignSystem"]),
        .target(name: "Profile", dependencies: ["Core", "Networking", "DesignSystem"]),
        .target(name: "Settings", dependencies: ["Core", "DesignSystem"]),
        .testTarget(name: "HomeTests", dependencies: ["Home"]),
        .testTarget(name: "ProfileTests", dependencies: ["Profile"]),
        .testTarget(name: "SettingsTests", dependencies: ["Settings"]),
    ]
)
```

**`Packages/DesignSystem/Package.swift`:**

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DesignSystem",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "DesignSystem", targets: ["DesignSystem"]),
    ],
    dependencies: [
        .package(path: "../Core"),
    ],
    targets: [
        .target(
            name: "DesignSystem",
            dependencies: ["Core"],
            resources: [.process("Resources/")]  // colors, fonts, images
        ),
        .testTarget(name: "DesignSystemTests", dependencies: ["DesignSystem"]),
    ]
)
```

Key SPM details (see the [SPM guide](swift-package-manager-guide_claude.md) for full reference):
- Resources use `.process()` for platform-optimized handling, `.copy()` for verbatim
- Access resources via `Bundle.module` at runtime
- Linting via build tool plugins: `plugins: [.plugin(name: "SwiftLintBuildToolPlugin", package: "SwiftLintPlugins")]`
- Platform-conditional dependencies: `.when(platforms: [.iOS])`

### Step 3: Minimal `project.yml`

This is the entire XcodeGen config. It only knows about the app shell and which packages to import:

```yaml
name: MyApp

options:
  bundleIdPrefix: com.mycompany
  deploymentTarget:
    iOS: "17.0"
  createIntermediateGroups: true

packages:
  Core:
    path: Packages/Core
  Networking:
    path: Packages/Networking
  Features:
    path: Packages/Features
  DesignSystem:
    path: Packages/DesignSystem

targets:
  MyApp:
    type: application
    platform: iOS
    sources:
      - App/Sources
    resources:
      - App/Resources
    dependencies:
      - package: Features
        products: [Home, Profile, Settings]
      - package: DesignSystem
    info:
      path: App/Info.plist
      properties:
        UILaunchStoryboardName: LaunchScreen
        UISupportedInterfaceOrientations:
          - UIInterfaceOrientationPortrait
    entitlements:
      path: App/MyApp.entitlements
      properties:
        com.apple.security.application-groups:
          - group.com.mycompany.myapp
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.mycompany.myapp
        CODE_SIGN_STYLE: Automatic
        DEVELOPMENT_TEAM: ABCDE12345
    scheme:
      testTargets:
        - MyAppTests
        - MyAppUITests

  MyAppTests:
    type: bundle.unit-test
    platform: iOS
    sources:
      - App/Tests
    dependencies:
      - target: MyApp

  MyAppUITests:
    type: bundle.ui-testing
    platform: iOS
    sources:
      - App/UITests
    dependencies:
      - target: MyApp
```

Notice what's NOT here:
- No framework targets — SPM handles modules
- No dependency wiring between Core/Networking/Features — `Package.swift` handles that
- No source excludes or compiler flags — `Package.swift` handles those too
- No external dependency URLs or versions — declared in each package's `Package.swift`

You only list packages the app directly imports. If `Home` depends on `Core` internally, the app doesn't need `- package: Core` unless `App/Sources/` also `import Core`.

### Step 4: Generate and Go

```bash
brew install xcodegen
xcodegen generate
echo -e "*.xcodeproj\n.build/" >> .gitignore
open MyApp.xcodeproj
```

### Step 5: Day-to-Day Workflow

- **Adding code** — create files in `Packages/*/Sources/` — SPM picks them up automatically, no regeneration needed
- **Adding a new package** — create `Packages/NewModule/Package.swift`, add to `project.yml` packages + dependencies, run `xcodegen generate`
- **Adding a new external dependency** — add to the relevant `Package.swift`, Xcode resolves automatically
- **Regenerate** — only needed when: adding/removing a package from `project.yml`, changing app-level settings, modifying schemes

## What Goes Where

| SPM packages own | XcodeGen app target owns |
|---|---|
| All Swift code (models, services, views, features) | `@main` entry point + root wiring |
| Unit tests (`swift test`) | UI tests (XCUITest) |
| External dependencies (Alamofire, etc.) | App icon / launch screen |
| Internal dependency graph | Info.plist (permissions, orientations) |
| Resources via `Bundle.module` | Entitlements (app groups, push, etc.) |
| Build tool plugins (SwiftLint, codegen) | Code signing / team / provisioning |
| Swift language settings | Build schemes |
| Platform-conditional compilation | App-level build scripts (if any) |

## Variant: Mono-Package

If separate packages per layer feels like overkill, use one package with multiple targets:

**`Packages/App/Package.swift`:**

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AppModules",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "Core", targets: ["Core"]),
        .library(name: "Networking", targets: ["Networking"]),
        .library(name: "DesignSystem", targets: ["DesignSystem"]),
        .library(name: "Home", targets: ["Home"]),
        .library(name: "Profile", targets: ["Profile"]),
        .library(name: "Settings", targets: ["Settings"]),
    ],
    dependencies: [
        .package(url: "https://github.com/Alamofire/Alamofire", from: "5.9.0"),
    ],
    targets: [
        .target(name: "Core"),
        .target(name: "Networking", dependencies: ["Core", "Alamofire"]),
        .target(name: "DesignSystem", dependencies: ["Core"]),
        .target(name: "Home", dependencies: ["Core", "Networking", "DesignSystem"]),
        .target(name: "Profile", dependencies: ["Core", "Networking", "DesignSystem"]),
        .target(name: "Settings", dependencies: ["Core", "DesignSystem"]),
        .testTarget(name: "CoreTests", dependencies: ["Core"]),
        .testTarget(name: "NetworkingTests", dependencies: ["Networking"]),
        .testTarget(name: "HomeTests", dependencies: ["Home"]),
    ]
)
```

**`project.yml`** shrinks to:

```yaml
name: MyApp

options:
  deploymentTarget:
    iOS: "17.0"

packages:
  AppModules:
    path: Packages/App

targets:
  MyApp:
    type: application
    platform: iOS
    sources: [App/Sources]
    resources: [App/Resources]
    dependencies:
      - package: AppModules
        products: [Home, Profile, Settings]
    info:
      path: App/Info.plist
      properties:
        UILaunchStoryboardName: LaunchScreen
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.mycompany.myapp
        CODE_SIGN_STYLE: Automatic
        DEVELOPMENT_TEAM: ABCDE12345
```

**Tradeoffs:**
- Simpler file structure, one `Package.swift` to maintain
- `swift test` runs all tests together (slower per iteration)
- Can't version/release individual layers independently
- Good enough for most apps; split later if needed

## Multi-Platform (iOS + macOS)

Packages handle this natively — just declare platforms in `Package.swift`:

```swift
platforms: [.iOS(.v17), .macOS(.v14)]
```

The XcodeGen side uses `supportedDestinations` for a unified target:

```yaml
targets:
  MyApp:
    type: application
    platform: auto
    supportedDestinations: [iOS, macOS]
    sources: [App/Sources]
    resources: [App/Resources]
    dependencies:
      - package: Features
        products: [Home, Profile, Settings]
```

Or separate targets per platform if you need different settings:

```yaml
targets:
  MyApp-iOS:
    type: application
    platform: iOS
    sources: [App/Sources]
    dependencies:
      - package: Features
        products: [Home, Profile]
  MyApp-macOS:
    type: application
    platform: macOS
    sources: [App/Sources]
    dependencies:
      - package: Features
        products: [Home, Profile]
```

Platform-specific code in packages uses `#if canImport(UIKit)` / `#if os(macOS)` or conditional target dependencies (see SPM guide).

## Testing Strategy

### Package Tests — Fast, No Xcode

```bash
# Test one package
cd Packages/Core && swift test

# Test all packages (from repo root)
for pkg in Packages/*/; do (cd "$pkg" && swift test); done
```

These run without Xcode, without a simulator, without code signing. Fast CI feedback.

### App Integration Tests — XcodeGen Target

```yaml
targets:
  MyAppTests:
    type: bundle.unit-test
    platform: iOS
    sources: [App/Tests]
    dependencies:
      - target: MyApp
```

For testing app-level wiring, navigation, dependency injection. Runs in simulator.

### UI Tests

```yaml
targets:
  MyAppUITests:
    type: bundle.ui-testing
    platform: iOS
    sources: [App/UITests]
    dependencies:
      - target: MyApp
```

### CI Pipeline

```bash
# Fast feedback — parallel package tests (no Xcode needed)
for pkg in Packages/*/; do
  (cd "$pkg" && swift test) &
done
wait

# App build + integration/UI tests
xcodegen generate
xcodebuild test \
  -project MyApp.xcodeproj \
  -scheme MyApp \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro'
```

## Build Scripts vs SPM Plugins

Prefer SPM build tool plugins when possible — they're portable, require no XcodeGen config, and run during `swift build` too:

```swift
// In any Package.swift target
.target(
    name: "Core",
    plugins: [
        .plugin(name: "SwiftLintBuildToolPlugin", package: "SwiftLintPlugins"),
    ]
)
```

Use XcodeGen `preBuildScripts` only for app-level concerns that can't be a package plugin:

```yaml
targets:
  MyApp:
    preBuildScripts:
      - script: |
          # App-specific code generation that needs Xcode env vars
          "${BUILD_DIR}/../../SourcePackages/artifacts/swiftgen/swiftgen" \
            config run --config App/swiftgen.yml
        name: SwiftGen
        inputFiles:
          - $(SRCROOT)/App/Resources/en.lproj/Localizable.strings
        outputFiles:
          - $(DERIVED_FILE_DIR)/Strings.swift
```

## Adding Remote Dependencies

Remote deps are declared in SPM, not XcodeGen. XcodeGen only needs to know about local packages.

```swift
// In Packages/Networking/Package.swift
dependencies: [
    .package(url: "https://github.com/Alamofire/Alamofire", from: "5.9.0"),
]
```

If the app target needs a remote dependency directly (rare — most should go through a package):

```yaml
# project.yml — only if App/Sources/ directly imports it
packages:
  Sentry:
    url: https://github.com/getsentry/sentry-cocoa
    from: 8.0.0

targets:
  MyApp:
    dependencies:
      - package: Sentry
```

## Tips

- **Keep `App/Sources/` tiny** — if you're writing business logic here, it should be in a package
- **Don't redeclare transitive deps in `project.yml`** — only list packages that `App/Sources/` directly imports
- **Use `swift package dump-package`** to debug resolved dependency graphs
- **Local packages appear automatically** in Xcode's navigator under "Packages" — no `fileGroups` needed
- **Previews work** in local packages — no special config
- **Resources in packages** use `Bundle.module`, not `Bundle.main`
- **`swift package resolve`** to force dependency resolution without building
- **Regenerate rarely** — most changes (new files, code edits, even new SPM dependencies) don't require `xcodegen generate`
- **Commit `Package.resolved`** from each package for reproducible builds
