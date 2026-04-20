# The `/preview` Route Convention

A dedicated `/preview` route lets you iterate on pure views against **mock data** without needing the backend, live state, or real side effects. The same view components are reused by the real app, which swaps in a live data source.

## Why

Views often depend on data that's expensive, async, or hard to drive into specific states (long-running agents, partial failures, empty states, rare statuses). Iterating on CSS or layout against a live backend is slow, flaky, and often impossible to reach the state you want to design against.

The `/preview` route solves this by:

- **Decoupling views from data** — views take a `DataSource` interface; you can plug in a mock or the real thing.
- **Making states addressable** — expose the mock's mutators on `window.__tap__` so the agent can drive the page into any state via `browser eval`.
- **Sharing one implementation** — the view tree at `/` and `/preview` is the same code. Only the data source differs.

## Structure

```
src/
  App.tsx                   # wouter: /preview → Preview, else → Live
  data/
    tasks.ts                # DataSource interface + domain types
    mock.ts                 # MockDataSource implements DataSource
    live.ts                 # LiveDataSource implements DataSource (SSE / API)
    fixtures/               # static JSON / markdown used by mock
  views/                    # pure view components — no data fetching
    Layout.tsx
    TaskList.tsx
    ExpandedCard.tsx
    ...
  previews/
    Preview.tsx             # wires MockDataSource → views, installs __tap__
  live/
    Live.tsx                # wires LiveDataSource → views
```

Key rule: nothing under `views/` imports from `data/mock.ts` or `data/live.ts`. Views only depend on the `DataSource` interface and the domain types.

## The DataSource Interface

Define a single interface both mock and live implement:

```ts
// data/tasks.ts
export interface DashboardDataSource {
  tasks: TaskItem[];
  fetchWorklog(slug: string): Promise<string | null>;
  fetchTerminalHistory(slug: string): Promise<string | null>;
  // ... plus any action methods like setTaskStatus, removeTask, connectPTY
}
```

- Reads: properties or `fetch*` methods.
- Writes: action methods returning `Promise<void>` so the live side can round-trip to the server.
- Streams (e.g. PTY output, SSE): return a connection/unsubscribe handle.

Both `MockDataSource` and `LiveDataSource` implement this interface. The views never know which one they're talking to.

## The Mock

`MockDataSource` holds plain in-memory data and mutators. Fixtures live under `data/fixtures/` as static files (`?raw` imports for markdown, JSON imports for structured data). The mock's mutators should cover every state transition the UI can trigger.

```ts
// data/mock.ts
export class MockDataSource implements DashboardDataSource {
  tasks: TaskItem[] = [...MOCK_TASKS];

  addTask(task: TaskItem) { this.tasks = [task, ...this.tasks]; }
  setTaskStatus(slug: string, status: TaskStatus) { /* ... */ }
  removeTask(slug: string) { /* ... */ }
  async fetchWorklog(slug: string) { return FIXTURES[slug] ?? null; }
  connectPTY(id: string): PTYConnection { /* canned stream */ }
}
```

Keep the mock synchronous where possible — easier to step through states from the agent.

## The Preview Page

`Preview.tsx` instantiates `MockDataSource`, renders the same view tree the live page renders, and installs `window.__tap__` so the agent can drive it:

```tsx
// previews/Preview.tsx
const dataSource = new MockDataSource();

function installTap(ds: MockDataSource, refresh: () => void) {
  (window as any).__tap__ = {
    __doc__: `
# dashboard preview — window.__tap__
- tasks                       current TaskItem[]
- addTask(task)               add a mock task
- setTaskStatus(slug, status) change a task's status
- removeTask(slug)            remove a task
- setDark(on)                 toggle dark mode
- refresh()                   force re-render
    `.trim(),
    get tasks() { return ds.tasks; },
    addTask(t: TaskItem) { ds.addTask(t); refresh(); },
    setTaskStatus(slug, status) { ds.setTaskStatus(slug, status); refresh(); },
    removeTask(slug) { ds.removeTask(slug); refresh(); },
    setDark(on: boolean) { document.documentElement.classList.toggle("dark", on); },
    refresh,
  };
}

export function Preview() {
  const [, setTick] = useState(0);
  const refresh = useCallback(() => setTick(n => n + 1), []);
  useEffect(() => { installTap(dataSource, refresh); }, [refresh]);

  // ... render the same <Layout>/<TaskList>/<ExpandedCard> tree as Live.tsx
}
```

Tap API conventions (see [Web Tap API Guide](web-tap-api.md)):

- Expose **mutators**, not setters — `addTask(t)` not `setTasks(list)`.
- Include a **`__doc__`** string so the agent can discover the surface with `browser eval '__tap__.__doc__'`.
- Every mutator calls `refresh()` so React re-reads the mock.

## Routing

Use wouter (or your router of choice) with a dedicated `/preview` path:

```tsx
// App.tsx
import { Route, Switch } from "wouter";
import { Preview } from "./previews/Preview";
import { Live } from "./live/Live";

export function App() {
  return (
    <Switch>
      <Route path="/preview" component={Preview} />
      <Route><Live /></Route>
    </Switch>
  );
}
```

The real app lives at `/`, the preview at `/preview`. The preview is bundled in dev and (optionally) prod — it's a valuable reference for anyone onboarding.

## Dev Workflow

```bash
# 1. Start the dev server with an explicit port
vp dev --port 5173

# 2. Open the preview
browser open http://localhost:5173/preview     # → session key a3f2

# 3. Drive states via __tap__ and screenshot each
browser eval -s a3f2 '__tap__.setTaskStatus("foo", { type: "running", agent: { id: "abc" } })'
browser screenshot -s a3f2 -o "$(tmpfile running.png)"

browser eval -s a3f2 '__tap__.setDark(true)'
browser screenshot -s a3f2 -o "$(tmpfile dark.png)"

# Or sweep states in one shot
browser screenshot --open http://localhost:5173/preview \
  -o "$(tmpfile states.png)" \
  --steps '
- wait: __tap__
- eval: __tap__.setTaskStatus("foo", { type: "rfc" })
- eval: __tap__.setDark(true)
'
```

## When to Use This Pattern

Use a `/preview` route when:

- Views are non-trivial and you want to iterate on them without a backend.
- States are hard to reach live (error branches, rare statuses, empty/loading/failed).
- You want visual regression screenshots that don't depend on live data.

Skip it for trivial pages or when the backend is cheap to run and always drives the views through every state anyway.

## Pitfalls

- **Don't let views import the mock.** The whole point is that views are data-source-agnostic. Keep the import graph `views/` → `data/tasks.ts` (types + interface) only.
- **Don't diverge the live and preview render trees.** If `Preview.tsx` and `Live.tsx` start rendering different layouts, the preview stops being a faithful testbed. Extract shared wiring into a helper or a `<Dashboard dataSource={ds}/>` component.
- **Keep fixtures realistic.** A mock that only covers the happy path doesn't help you find layout bugs. Include long strings, empty lists, pending/error states, dark mode.
- **Refresh on mutation.** MobX observers re-render for free; plain React needs an explicit `refresh()` in each tap mutator (see above).

## Reference Implementation

See [agentboss/dashboard](https://github.com/hayeah/agentboss/tree/master/dashboard/src):

- `data/tasks.ts` — `DashboardDataSource` interface.
- `data/mock.ts` — `MockDataSource` with in-memory mutators and fixtures.
- `data/live.ts` — `LiveDataSource` with SSE + API calls.
- `previews/Preview.tsx` — preview wiring + `__tap__` install.
- `live/Live.tsx` — live wiring.
- `views/` — shared view components.
