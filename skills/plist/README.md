---
name: plist
description: Explore macOS plist preferences with layered inspection and fuzzy domain search. Use when inspecting app defaults, finding preference domains, or understanding plist layer precedence.
---

# plist

Explore macOS plist preferences without memorizing file paths or `defaults` incantations. Resolves domains to their backing files across all layers (managed, user, system, byhost, sandbox) and renders them as colorized, truncated JSON.

## Install

```bash
cd skills/plist
uv tool install -e . \
  --with "hayeah-core @ file:///path/to/dotfiles/hayeah" \
  --with "jsoninspect @ file:///path/to/dotfiles/skills/jsoninspect"
```

## Commands

### `plist inspect <domain>`

Read all plist layers for a domain and print as colorized JSON.

```bash
# Inspect Dock preferences across all layers
plist inspect com.apple.dock

# Inspect Finder preferences
plist inspect com.apple.finder

# Inspect global preferences (NSGlobalDomain is an alias for .GlobalPreferences)
plist inspect NSGlobalDomain

# Inspect a plist file directly by path
plist inspect ~/Library/Preferences/com.apple.dock.plist

# Truncate long strings at 40 chars instead of default 80
plist inspect com.apple.dock -s 40

# Inspect trackpad gesture configuration
plist inspect com.apple.AppleMultitouchTrackpad

# Inspect keyboard/input source settings (often has user + system layers)
plist inspect com.apple.HIToolbox

# Inspect a third-party app
plist inspect com.raycast.macos
```

Output shows each layer with a `//` comment header (HJSON-compatible):

```
// user: ~/Library/Preferences/com.apple.dock.plist
{
  "autohide": true,
  "tilesize": 49,
  ...
}

// system: /Library/Preferences/com.apple.dock.plist
{
  "DesktopAdminImageGenerationNumber": {
    "GenerationNumber": 2
  }
}
```

Only layers that exist on disk are printed. Missing layers are omitted silently.

### `plist which <pattern>`

Find domains matching a fuzzy pattern and show which layer files exist.

```bash
# Find all dock-related domains
plist which dock

# Find either dock or finder domains
plist which 'dock ; finder'

# Find non-Apple third-party app domains
plist which '!apple'

# Find all domains (no pattern)
plist which

# Find domains with "trackpad" in the name
plist which trackpad
```

Uses fzf extended-search syntax (via `hayeah.core.fzfmatch`):

- Space-separated terms are implicit AND
- `|` for compound AND (intersection), `;` for union OR
- `!` prefix for negation, `^`/`$` for anchors, `'` for word boundaries

## Layer Precedence

Layers are printed in precedence order (highest first):

- `managed` — `~/Library/Managed Preferences/<domain>.plist` (MDM/enterprise)
- `user` — `~/Library/Preferences/<domain>.plist` (most common)
- `system` — `/Library/Preferences/<domain>.plist` (system-wide defaults)
- `byhost` — `~/Library/Preferences/ByHost/<domain>.<hw-uuid>.plist` (per-machine)
- `sandbox` — `~/Library/Containers/<domain>/Data/Library/Preferences/<domain>.plist` (sandboxed apps)

## Data Representation

Non-JSON plist types use `@type:` prefix conventions:

- `bytes` (≤64 bytes) → `"@data:DEADBEEF"` (hex)
- `bytes` (>64 bytes) → `"@data:<512 bytes>"` (size only)
- `datetime` → `"@date:2026-03-19T10:00:00+00:00"` (ISO 8601)
- All other types (dict, array, string, int, float, bool) map directly to JSON

## Options

- `--max-string`, `-s` — Max string length before truncation (default: 80)

## Domain Aliases

- `NSGlobalDomain`, `-g`, `-globalDomain` all resolve to `.GlobalPreferences`

## Quirks

- Domain list is gathered by globbing `~/Library/Preferences/*.plist` — domains that only exist at system level won't appear in `plist which` results
- Some system-level plists may be unreadable without sudo (silently skipped)
- Integer fields named `*-mod-date` in Dock plists are not timestamps — they're internal counters that look like dates but aren't
- Binary plist format is handled transparently (most plists on disk are binary)
