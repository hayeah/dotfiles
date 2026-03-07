# google/wire — Compile-Time Dependency Injection for Go

Wire is a code generation tool for compile-time dependency injection in Go. It analyzes provider functions, builds a dependency graph, and generates plain Go code with no runtime reflection.

**Status:** Archived (Aug 2025). Maintained fork: [goforj/wire](https://github.com/goforj/wire). API-compatible drop-in replacement.

## Install

```bash
go install github.com/google/wire/cmd/wire@latest
```

## Core Concepts

### Providers

Functions that produce a value. Dependencies are expressed as parameters.

```go
func NewUserRepo(db *sql.DB) *UserRepo {
    return &UserRepo{db: db}
}
```

Providers can return errors and cleanup functions:

```go
func NewDB(cfg DatabaseURL) (*sql.DB, func(), error) {
    db, err := sql.Open("postgres", string(cfg))
    if err != nil {
        return nil, nil, err
    }
    return db, func() { db.Close() }, nil
}
```

### Provider Sets

Group related providers together for reuse:

```go
var RepoSet = wire.NewSet(
    NewUserRepo,
    NewPostRepo,
    wire.Bind(new(UserRepository), new(*UserRepo)),
)
```

### Injectors

Stub functions that declare the dependency graph. Wire generates the implementation.

**`wire.go`** (build-tagged to exclude from normal builds):

```go
//go:build wireinject

package main

import "github.com/google/wire"

func InitializeApp(cfg *Config) (*App, func(), error) {
    wire.Build(
        serverSet,
        serviceSet,
        repoSet,
        dataSet,
    )
    return nil, nil, nil
}
```

Run `wire` to generate `wire_gen.go` with the real implementation.

## API Reference

| Function | Purpose |
|---|---|
| `wire.NewSet(...)` | Group providers into a reusable set |
| `wire.Build(...)` | Declare injector dependencies (inside injector stub) |
| `wire.Bind(new(Iface), new(*Impl))` | Bind interface to concrete type |
| `wire.Struct(new(T), fields...)` | Auto-fill struct fields as injection |
| `wire.FieldsOf(new(T), fields...)` | Extract struct fields as providers |
| `wire.Value(v)` | Bind a literal value to its type |
| `wire.InterfaceValue(new(I), v)` | Bind a literal value to an interface type |

## CLI Commands

```bash
wire              # same as wire gen
wire gen ./...    # generate wire_gen.go files
wire check ./...  # validate without generating
wire diff ./...   # show diff between current and would-be-generated
wire show ./...   # display provider set info
```

## Recommended Project Setup

Based on the **Kratos layout** (most widely adopted convention) and community best practices.

### Directory Structure

```
cmd/
  server/
    main.go              # entry point, calls InitializeApp()
    wire.go              # injector stub: wire.Build(all sets)
    wire_gen.go          # generated (committed to repo)

internal/
  conf/
    conf.go              # Config struct, NewConfig() provider
                         # var ProviderSet = wire.NewSet(NewConfig)

  server/
    server.go            # HTTP/gRPC server providers
                         # var ProviderSet = wire.NewSet(NewHTTPServer, NewGRPCServer)

  service/
    service.go           # Application services (orchestration layer)
                         # var ProviderSet = wire.NewSet(NewUserService, NewPostService)

  biz/
    biz.go               # Domain/business logic, use case providers
                         # var ProviderSet = wire.NewSet(NewUserUsecase)

  data/
    data.go              # Database, cache, external API clients
                         # var ProviderSet = wire.NewSet(NewData, NewUserRepo)
```

### Key Conventions

**One `ProviderSet` per package:**

```go
// internal/data/data.go
package data

var ProviderSet = wire.NewSet(
    NewData,
    NewUserRepo,
    NewPostRepo,
    wire.Bind(new(biz.UserRepository), new(*UserRepo)),
)
```

**Single injector in `cmd/`:**

```go
//go:build wireinject

package main

import (
    "myapp/internal/conf"
    "myapp/internal/data"
    "myapp/internal/biz"
    "myapp/internal/service"
    "myapp/internal/server"
)

func InitializeApp(cfgPath string) (*App, func(), error) {
    wire.Build(
        conf.ProviderSet,
        data.ProviderSet,
        biz.ProviderSet,
        service.ProviderSet,
        server.ProviderSet,
        NewApp,
    )
    return nil, nil, nil
}
```

**Typed wrappers for primitives** — avoid bare `string`, `int` in provider signatures:

```go
type DatabaseURL string
type ListenAddr string
type JWTSecret []byte
```

**Multi-binary projects** get separate injectors:

```
cmd/
  api-server/wire.go      # API server injector
  worker/wire.go           # Background worker injector
  cli/wire.go              # CLI tool injector
```

### Config Injection Pattern

Consolidate config reading in one place. Downstream providers receive typed values.

```go
// internal/conf/conf.go
type Config struct {
    DatabaseURL DatabaseURL
    ListenAddr  ListenAddr
    JWTSecret   JWTSecret
}

func NewConfig(path string) (*Config, error) {
    // read from file, env vars, flags
}

var ProviderSet = wire.NewSet(
    NewConfig,
    wire.FieldsOf(new(*Config), "DatabaseURL", "ListenAddr", "JWTSecret"),
)
```

### Interface Binding Pattern

Providers return concrete types. Bind to interfaces in the same ProviderSet.

```go
// internal/data/user_repo.go
type UserRepo struct{ db *sql.DB }

func NewUserRepo(db *sql.DB) *UserRepo {
    return &UserRepo{db: db}
}

func (r *UserRepo) FindByID(id int) (*User, error) { /* ... */ }

// internal/data/data.go
var ProviderSet = wire.NewSet(
    NewUserRepo,
    wire.Bind(new(biz.UserRepository), new(*UserRepo)),
)
```

### Testing

- **Unit tests:** Skip wire entirely. Construct with mocks manually.
- **Integration tests:** Create a test-only injector in a `wire_test.go` file, passing mocks as arguments.

```go
//go:build wireinject

package integration

func InitializeTestApp(mockRepo biz.UserRepository) (*App, func(), error) {
    wire.Build(
        service.ProviderSet,
        server.ProviderSet,
        NewApp,
    )
    return nil, nil, nil
}
```

### CI Integration

Ensure generated code stays in sync:

```bash
wire ./... && git diff --exit-code
```

## Anti-Patterns to Avoid

- **Giant monolithic ProviderSets** — split by package/layer
- **Bundling shared types** like `*http.Client` or `*sql.DB` in library sets — let consumers provide these
- **Bare primitives** in provider signatures — use typed wrappers (`DatabaseURL`, not `string`)
- **Not committing `wire_gen.go`** — the generated code should be in version control so builds work without wire installed
- **Using wire for trivial apps** — manual DI is simpler when you have < 10 providers

## Notable Projects Using Wire

- **[go-kratos](https://github.com/go-kratos/kratos)** — microservice framework, wire baked into scaffold
- **[go-cloud](https://github.com/google/go-cloud)** — wire's original driving use case
- **[Wild Workouts](https://github.com/ThreeDotsLabs/wild-workouts-go-ddd-example)** — DDD/CQRS example app

## References

- [Official guide](https://github.com/google/wire/blob/main/docs/guide.md)
- [Best practices](https://github.com/google/wire/blob/main/docs/best-practices.md)
- [FAQ](https://github.com/google/wire/blob/main/docs/faq.md)
- [Go blog post](https://go.dev/blog/wire)
- [Kratos layout template](https://github.com/go-kratos/kratos-layout)
- [goforj/wire (maintained fork)](https://github.com/goforj/wire)
