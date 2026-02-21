# TypeScript project

Toolings and style guide for creating TypeScript projects.

## Toolings

- Use vite/vitest for build.
- Use oxfmt, oxlint for linting.
  - https://oxc.rs
- Use bun to run TypeScript code by defaut.
  - Avoid bun specific code.

## Typescript Class

- how you should write typescript class
  - Use `constructor(public foo: str, public bar number)` to declare and assign to instance properties
  - Prefer composition & injection into the constructor, rather than constructing complex classes inside the constructor
  - if a property requires async to initialize, create an async factory method on the class, then inject the awaited value into a normal constructor
    - this avoids an `init` instance method
  - Example code:

```
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

## File Naming Convention

- If a file primarily export a class or a component, name the file the same as the exported name.
  - For example `export BlobStore` should be named `BlobStore.ts`.
  - For example `export MyComponent` should be named `MyComponent.tsx`.
- test files (vitest) should be placed in the same directory as the source code.
  - tests for "src/BlobStore.ts" should be "src/BlobStore.test.ts"
- tests that should run in browser have the naming convention of: "src/BlobStore.test.browser.ts"
