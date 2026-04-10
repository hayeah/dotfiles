# supervisor — process supervision with dir-flock liveness

A reusable Go library for the supervisor pattern: dir-lock for liveness, atomic state.json, tmux window management, and pluggable service monitoring.

```go
import "github.com/hayeah/dotfiles/libs/hayeah-go/supervisor"
```

## The pattern

Each supervised process gets a **directory** as its sole state store. The directory itself is the lock. One JSON file holds all state.

```
<state-dir>/<key>/
  state.json    # all state — rewritten atomically on every change
```

Plugins can create additional files in the directory (e.g. `rpc.sock`, logs). The supervisor doesn't manage these — the plugin owns them.

### Two primitives

**Directory flock — liveness.** The supervisor holds an exclusive `flock` on the directory fd for its entire lifetime. This is the ground truth for "is this process alive":

- Acquire: `flock(LOCK_EX|LOCK_NB)` on the dir fd at startup
- Probe: try to acquire from another process — `EWOULDBLOCK` means alive
- Release: close the fd (OS releases automatically on crash)

The flock is advisory and doesn't prevent creating files inside the directory — plugins can freely create sockets, logs, etc.

**state.json — all state in one file.** Written atomically (tmp + rename) by the supervisor on every state change. Two namespaced sections:

```json
{
  "supervisor": {
    "key": "vite",
    "spawn": { "session": "agent-r19", "window": "vite", "cmd": [...] },
    "created_at": "2026-04-10T12:00:00Z"
  },
  "service": {
    "state": "healthy",
    "port": 20042,
    "health": { "status": 200, "latency_ms": 12 }
  }
}
```

The `supervisor` section is owned by the library. The `service` section is owned by the plugin — the supervisor stores it opaquely as `json.RawMessage`.

### Why this works

- **No DB** — the filesystem IS the database
- **Crash safe** — OS releases flock on crash, no stale "running" state
- **Single writer** — flock guarantees one supervisor per directory
- **Observable** — `ls`, `cat`, `jq` work for inspection
- **Concurrent reads** — atomic tmp+rename means readers never see partial data

## Usage

```go
sup := supervisor.New(supervisor.SupervisorConfig{
    StateDir: ".devport",
    Key:      "vite",
    Spawn: supervisor.TmuxSpawn{
        Session: "agent-r19",
        Window:  "vite",
        Cmd:     []string{"pnpm", "exec", "vp", "dev", "--port", "20042"},
        CWD:     "/path/to/project",
        Env:     map[string]string{"VITE_PORT": "20042"},
    },
    Plugin:     myPlugin,  // implements supervisor.Plugin
    KillOnExit: true,
})
err := sup.Run(ctx)
```

### Reading state

```go
store := supervisor.NewStore(".devport")

// List all services
states, _ := store.List()

// Check if alive
alive := store.IsAlive("vite")

// Read state
state, _ := store.Load("vite")

// Prefix resolution
state, _ = store.Resolve("vi")
```

### Writing a plugin

The plugin owns the service lifecycle — health checks, sockets, restart policy. The supervisor provides `UpdateService()` to persist state and `StateDir` for any files the plugin needs.

```go
type MyPlugin struct {
    Port int
}

func (p *MyPlugin) Run(ctx context.Context, env supervisor.PluginEnv) error {
    // Report initial state
    env.UpdateService(map[string]any{"state": "starting", "port": p.Port})

    // Optionally serve on a unix socket in the state dir
    socketPath := filepath.Join(env.StateDir, "rpc.sock")
    listener, _ := net.Listen("unix", socketPath)
    defer listener.Close()
    // ... serve HTTP/gRPC/whatever on listener

    // Monitor and report state changes
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(5 * time.Second):
            env.UpdateService(map[string]any{"state": "healthy", "port": p.Port})
        }
    }
}
```

## Package contents

| File | Purpose |
|------|---------|
| `flock.go` | Dir flock acquire / probe / release |
| `atomic.go` | Atomic JSON write (tmp + rename) |
| `state.go` | StateFile, SupervisorState types |
| `store.go` | Store (read-side) + Writer (locked single-writer) |
| `tmux.go` | Tmux CLI wrapper |
| `poll.go` | Generic retry/poll utility |
| `tailfile.go` | Incremental file tailing |
| `plugin.go` | Plugin interface + PluginEnv |
| `supervisor.go` | Supervisor coordinator |
