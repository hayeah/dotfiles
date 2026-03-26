---
name: react
description: Conventions for building React projects — file organization, tooling, agent API, browser testing, and dev workflow.
globs:
  - "**/*.tsx"
  - "**/*.jsx"
  - vite.config.*
  - package.json
---

# React Project Conventions

How we set up, organize, and work with React projects.

## Project Setup

Stack:

- **Vite** — build and dev server
- **React + TypeScript**
- **Tailwind CSS** via `@tailwindcss/vite` plugin
- **wouter** — lightweight routing
- **MobX** + `mobx-react-lite` — state management
- **Framer Motion** — UI animations

Scaffold with:

```bash
bunx create-vite myproject --template react-ts
cd myproject
bun install
bun add wouter mobx mobx-react-lite framer-motion
bun add -d tailwindcss @tailwindcss/vite
```

### vite.config.ts

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

### Minimal global CSS

Keep `index.css` minimal — pages style themselves independently:

```css
@import "tailwindcss";

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #root { width: 100%; height: 100%; }
```

### Raw asset imports

Vite supports `?raw` for importing text files (shaders, SVGs, etc.):

```ts
import shaderSrc from './myShader.frag?raw'
```

Add type declarations in `src/raw.d.ts`:

```ts
declare module '*.frag?raw' { const src: string; export default src }
declare module '*.vert?raw' { const src: string; export default src }
```

## File Organization

Group code by feature/route path, not by semantic type:

```
src/
  App.tsx
  main.tsx
  index.css
  types.d.ts
  raw.d.ts
  pages/
    HomePage.tsx
    pixelate/              # one folder per experiment/feature
      PixelatePage.tsx     # page component
      webgl.ts             # helpers used by this page
      chuckClose.frag      # assets co-located
      kusamaDot.frag
    dashboard/
      DashboardPage.tsx
      DashboardStore.ts
      MetricsChart.tsx
```

Rules:

- **Co-locate** related code: components, stores, shaders, helpers all live in the same folder as the page that uses them
- **Don't** spread across `src/shaders/`, `src/stores/`, `src/components/` — that forces you to jump between directories for a single feature
- Project-wide types and declarations go in `src/`
- Shared utilities (if truly shared across features) go in `src/lib/`

## Routing

Use wouter with route params. Each experiment/feature gets a sub-route:

```tsx
import { Route, Switch, Redirect } from 'wouter'

export function App() {
  return (
    <Switch>
      <Route path="/" component={HomePage} />
      <Route path="/pixelate/:effect" component={PixelatePage} />
      <Route path="/pixelate"><Redirect to="/pixelate/chuck-close" /></Route>
      <Route>404</Route>
    </Switch>
  )
}
```

## Agent API (`window.__agent`)

Every page exposes a `window.__agent` object for browser automation. This is a per-route convention — each page registers on mount, cleans up on unmount.

### `__DOC__` string

Must be the first thing after imports. The agent reads it from source to know what's available:

```tsx
const __DOC__ = `
# MyPage

## window.__agent

- store — MobX observable
  - store.count (number)
  - store.query (string)
- $canvas — the canvas element
- loadImage(src) — load an image URL
`
```

### Naming conventions

- `$` prefix for DOM element refs: `$canvas`, `$searchInput`, `$scrollArea`
- Everything else is state, stores, or callbacks
- Use MobX observables for state — agents can read/write directly

### Implementation pattern

```tsx
const store = observable({ count: 0, query: '' })

export const MyPage = observer(() => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    window.__agent = {
      store,
      get $canvas() { return canvasRef.current },
      doSomething() { /* ... */ },
    }
    return () => { window.__agent = null }
  }, [])

  // ...
})
```

### Type declaration

In `src/types.d.ts`:

```ts
declare interface Window { __agent: any }
```

## Browser Testing with `/browser`

Use the `browser` skill to screenshot and interact with pages during development.

### Screenshots

```bash
# Basic screenshot
browser screenshot --open http://localhost:19003/mypage -o "$(tmpfile mypage.png)"

# Wait for content to load
browser screenshot --open http://localhost:19003/mypage -w 2000 -o "$(tmpfile mypage.png)"

# Modify state then screenshot
browser screenshot --open http://localhost:19003/mypage \
  -o "$(tmpfile mypage.png)" \
  -w 2000 \
  -e '__agent.store.count = 42'
```

### Multi-step screenshots

```bash
browser screenshot --open http://localhost:19003/mypage \
  -o "$(tmpfile steps.png)" \
  --steps '
- wait: "2000"
- eval: __agent.store.mode = "dark"
  wait: "500"
'
```

### Evaluating state

```bash
browser eval --open http://localhost:19003/mypage '__agent.store'
browser eval --open http://localhost:19003/mypage '__agent.doSomething()'
```

### Workflow

- Load default assets on mount so pages aren't blank when screenshotted
- Use `__agent` to drive state changes for screenshot comparisons
- Screenshot after changes to verify visually

## Dev Server with devport

Register the project in `~/.config/devport/devport.toml`:

```toml
[service."myproject"]
cwd = "~/github.com/hayeah/myproject"
command = ["bunx", "--bun", "vite", "--port", "${PORT}", "--host", "0.0.0.0"]
port = 19003
restart = "never"

[service."myproject".health]
type = "http"
url = "/"
expect_status = [200]
startup_timeout = "15s"
```

Key points:

- Always bind to `0.0.0.0` so the server is accessible externally (for tunnels, mobile testing)
- Use `devport start --key myproject` to start, `devport restart --key myproject` after config changes
- Use `devport freeport` to pick an available port

## Tooling Summary

- **Build/dev**: Vite (`bunx --bun vite`)
- **Package manager**: bun
- **Type check**: `npx tsc --noEmit`
- **Linting**: oxlint, oxfmt
- **State**: MobX (see typescript skill's react-mobx.md for patterns)
- **Styling**: Tailwind CSS — minimal global styles, pages self-contained
- **Routing**: wouter
- **Animation**: Framer Motion
- **Testing**: browser screenshots via `/browser` skill + `__agent` API
