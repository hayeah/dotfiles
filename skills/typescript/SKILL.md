---
name: typescript
description: Tooling and style guide for TypeScript projects.
---

# TypeScript project

Tooling and style guide for TypeScript projects.

## Tooling

- Use vite/vitest for build.
- Use oxfmt, oxlint for linting.
  - https://oxc.rs
- Use bun to run TypeScript by default.
  - Avoid bun-specific code.
- For complex state management, use mobx. See [./react-mobx.md](./react-mobx.md)

## Classes

- Use `constructor(public foo: string, public bar: number)` to declare and assign instance properties.
- Prefer composition and injection over constructing dependencies inside the constructor.
- For async initialization, use a static factory method that injects the awaited value into a normal constructor.
  - Avoids needing an `init` instance method.

Example:

```ts
private readonly dbName: string;
private readonly storeName: string;

constructor(
  private readonly db: IDBDatabase,
  config: BlobStoreConfig,
) {
  this.dbName = config.dbName;
  this.storeName = config.storeName;
}

static async create(config: BlobStoreConfig): Promise<BlobStore> {
  const dbName = config.dbName;
  const storeName = config.storeName;
  const version = BlobStore.CURRENT_DB_VERSION;

  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    // ...
  });

  return new BlobStore(db, config);
}
```

## File naming

- Name files after their primary export (class or component).
  - `BlobStore` → `BlobStore.ts`
  - `MyComponent` → `MyComponent.tsx`
- Place test files (vitest) in the same directory as source.
  - `src/BlobStore.ts` → `src/BlobStore.test.ts`
- Browser tests use the convention: `*.test.browser.ts`
