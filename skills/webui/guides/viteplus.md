---
overview: Comprehensive reference for Vite+ (viteplus.dev), the unified web toolchain by VoidZero that combines Vite, Vitest, Oxlint, Oxfmt, Rolldown, tsdown, and Vite Task into a single CLI.
tags:
  - reference
---

# Vite+ Guide

Vite+ is **The Unified Toolchain for the Web** by VoidZero. It consolidates runtime management, package management, dev server, build, lint, format, test, and task execution into a single `vp` CLI.

Built on: Vite, Vitest, Oxlint, Oxfmt, Rolldown, tsdown, Vite Task.

## Install

```bash
# macOS/Linux
curl -fsSL https://vite.plus | bash

# Windows PowerShell
irm https://vite.plus/ps1 | iex
```

After install, run `vp help` in a new terminal session.

## Quick Start

```bash
vp create       # scaffold new project
vp install      # install dependencies
vp dev          # dev server
vp check        # format + lint + type-check in one pass
vp test         # run tests
vp build        # production build
```

## Command Reference

### Start Phase

- `vp create` - scaffold a new project
- `vp migrate` - migrate existing Vite/Vitest/ESLint/Prettier setup to Vite+
- `vp config` - configure Vite+ for current project (installs git hooks, etc.)
- `vp install` - install dependencies
- `vp env` - manage Node.js runtime versions

### Develop Phase

- `vp dev` - Vite dev server (standard Vite experience)
- `vp check` - unified format + lint + type-check
- `vp check --fix` - auto-fix formatting and lint issues
- `vp lint` - lint only (Oxlint)
- `vp fmt` - format only (Oxfmt)
- `vp test` - run tests (Vitest)

### Execute Phase

- `vp run <script>` - run package.json scripts or config tasks
- `vp run` (no args) - interactive task selection
- `vp cache` - manage task cache
- `vp vpx` / `vp exec` / `vp dlx` - execute packages

### Build Phase

- `vp build` - production build (Vite + Rolldown)
- `vp pack` - package libraries (tsdown)
- `vp preview` - serve production build locally

### Dependencies

- `vp add` / `vp remove` / `vp update` / `vp dedupe` / `vp outdated` / `vp why` / `vp info`

### Maintenance

- `vp upgrade` - upgrade Vite+
- `vp implode` - remove Vite+

**Note:** These commands are built-in and cannot be overridden. Use `vp run <name>` to run package.json scripts.

## Configuration

Everything lives in a single `vite.config.ts`:

```typescript
import { defineConfig } from 'vite-plus';

export default defineConfig({
  // Standard Vite options
  server: {},
  build: {},
  preview: {},

  // Vite+ extensions
  test: {},    // Vitest
  lint: {},    // Oxlint
  fmt: {},     // Oxfmt
  run: {},     // Vite Task
  pack: {},    // tsdown
  staged: {},  // pre-commit checks
});
```

### Lint Config

```typescript
lint: {
  ignorePatterns: ['dist/**'],
  options: {
    typeAware: true,   // enable type-aware linting
    typeCheck: true,    // TypeScript type checking via tsgo
  },
  rules: {
    'no-console': ['error', { allow: ['error'] }],
  },
}
```

- `typeAware` + `typeCheck` are recommended (enabled by default in `vp create`/`vp migrate`)
- 600+ ESLint-compatible rules via Oxlint
- ~50-100x faster than ESLint

### Format Config

```typescript
fmt: {
  ignorePatterns: ['dist/**'],
  singleQuote: true,
  semi: true,
  experimentalSortPackageJson: true,
}
```

- Prettier-compatible via Oxfmt
- ~30x faster than Prettier

### Test Config

```typescript
test: {
  include: ['src/**/*.test.ts'],
}
```

- **Do not** use `vitest.config.ts` with Vite+ -- put everything in `vite.config.ts`
- `vp test` does NOT enter watch mode by default (unlike standalone Vitest)
- `vp test watch` for watch mode
- `vp test run --coverage` for coverage
- Change imports: `from 'vitest'` -> `from 'vite-plus/test'`
- Browser mode, snapshot tests, type tests, visual regression all supported

### Run/Task Config

```typescript
run: {
  enablePrePostScripts: true,  // default: true (workspace root only)
  cache: {
    scripts: false,  // package.json scripts not cached by default
    tasks: true,     // config tasks cached by default
  },
  tasks: {
    myTask: {
      command: 'echo hello',
      dependsOn: ['lint', 'test'],  // run these first
      cache: true,                   // default for tasks
      env: ['VITE_*'],              // env vars in cache fingerprint
      untrackedEnv: ['HOME'],       // passed but not fingerprinted
      input: [{ auto: true }],      // file tracking for cache
      cwd: '.',                     // working directory
    },
  },
}
```

**Workspace/monorepo features:**
- `vp run @my/app#build` - target specific package
- `vp run -w build` - run from workspace root
- `vp run -r build` - recursive across all packages
- `vp run -t build` - transitive (package + all deps)
- `--filter` - select packages by name/glob/directory (pnpm syntax)
- `-v` - verbose with cache statistics
- Commands with `&&` auto-split into independent cached sub-tasks

### Pack Config (Library Packaging)

```typescript
pack: {
  dts: true,                // generate .d.ts files
  format: ['esm', 'cjs'],  // output formats
  sourcemap: true,
}
```

- `vp pack` for libraries, `vp build` for web apps
- DTS generation and bundling
- Auto-generates package.json exports
- Standalone executables via `exe: true`
- Watch mode: `vp pack --watch`

### Staged (Pre-commit Hooks)

```typescript
staged: {
  '*.{js,ts,tsx,vue,svelte}': 'vp check --fix',
}
```

- Replaces `lint-staged` -- centralized in `vite.config.ts`
- `vp config` installs git hooks to `.vite-hooks/`
- `vp staged` runs checks on git-staged files
- Flags: `--verbose`, `--fail-on-changes`

## Environment/Runtime Management

`vp env` manages Node.js versions globally and per-project.

```bash
vp env setup          # create shims in ~/.vite-plus/bin
vp env on/off         # toggle managed vs system-first mode
vp env pin <version>  # create .node-version file
vp env install        # install pinned Node version
vp env doctor         # diagnostic checks
```

**Managed mode** (default): shims always use Vite+-managed Node.js.
**System-first mode**: prefer system Node, fall back to managed.

Runtimes stored in `~/.vite-plus` (configurable via `VITE_PLUS_HOME`).

## Migration from Existing Setup

```bash
vp migrate              # migrate current directory
vp migrate <path>       # migrate specific directory
vp migrate --no-interactive
```

**Options:**
- `--agent <name>` - write agent instructions
- `--editor <name>` - write editor config
- `--hooks` - set up pre-commit hooks

**Pre-migration:**
- Upgrade to Vite 8+ and Vitest 4.1+ first

**Post-migration checklist:**
```bash
vp install
vp check
vp test
vp build
```

**Import changes:**
- `from 'vitest'` -> `from 'vite-plus/test'`
- `from '@vitest/browser/context'` -> `from 'vite-plus/test/browser/context'`

**Config consolidation:**
- Move tsdown config into `pack` block, delete `tsdown.config.ts`
- Move lint-staged config into `staged` block

**Caveat:** Most projects need manual adjustments after `vp migrate`.

## Build

```bash
vp build              # production build
vp build --watch      # watch mode
vp build --sourcemap  # with source maps
vp preview            # serve production output locally
```

- Uses Vite 8 + Rolldown
- ~40x faster than webpack
- Standard Vite configuration applies
- `vp build` always runs built-in Vite build; use `vp run build` for package.json scripts

## Dev Server

```bash
vp dev
```

- Standard Vite dev server
- Always-instant HMR
- Opt-in full-bundle dev mode for large apps
- Configure via standard Vite `server` options

## Framework Support

Works with all Vite-based frameworks: React, Vue, Svelte, Solid.js, 20+ more.
Supports meta-frameworks shipped as Vite plugins.
Deploy to: Vercel, Netlify, Cloudflare, Render, Nitro.

## CI Setup

Use the `setup-vp` GitHub Action for CI environments.

## Performance Claims

- ~40x faster production builds than webpack
- ~50-100x faster linting than ESLint
- ~30x faster formatting than Prettier
- Rust-based low-level components (Oxc, Rolldown)

## License

Free and open source under MIT license.
