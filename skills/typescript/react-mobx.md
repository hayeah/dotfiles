# React Coding Guide (MobX-focused)

## Keep components “dumb”

* Treat UI components as render functions: they receive state via MobX stores (or props when absolutely necessary) and emit events

  ```tsx
  import { observer } from "mobx-react-lite"
  import { useReaderStore } from "../stores/RootStore"

  const ChapterTitle = observer(() => {
    const readerStore = useReaderStore()
    return <h1>{readerStore.currentChapterTitle}</h1>
  })
  ```
* Prefer importing a store over drilling a long prop chain
  *Good*

  ```tsx
  const SidebarToggle = observer(() => {
    const readerStore = useReaderStore()
    const toggle = () => readerStore.toggleSidebar()
    return <button onClick={toggle}>Toggle</button>
  })
  ```

  *Avoid*

  ```tsx
  // passing through three layers
  <ChapterHeader
    isOpen={isOpen}
    onToggle={toggleSidebar}
  />
  ```
* Side-effects belong in stores or at most in a thin “controller” component. UI components should rarely need `useEffect`.
* Co-locate view logic with the component; move business logic to the store.

## Minimise `useEffect`

* Ask: “Does this effect trigger an imperative browser API?” If not, it probably belongs in computed state or in the store.
* Derive values instead of setting local state.

  ```tsx
  // Instead of:
  const [filtered, setFiltered] = useState<Book[]>([])
  useEffect(() => {
    setFiltered(all.filter(b => b.title.includes(query)))
  }, [all, query])
  // Prefer:
  const filtered = useMemo(
    () => all.filter(b => b.title.includes(query)),
    [all, query],
  )
  ```
* When you **do** need an effect, keep the dependency list short and the callback pure (return a cleanup when needed).

## Minimise `useState`

* MobX observable state is usually enough.
* Local state is fine for ephemeral UI details (hover, open/closed) that never matter outside the component.
* If you see `useState` just mirroring a store value, remove it.

## One component per file

* Name the file the same as the component (`Sidebar.tsx` contains `Sidebar`).
* For complex features, create a folder:

  ```
  reader/
    Reader.tsx        // public entry
    Nav.tsx
    Sidebar.tsx
    ChapterContent.tsx
  ```
* Keep tests next to the file (`Sidebar.test.tsx`) or in a `__tests__` folder.

## Handling async data in MobX stores

* Put **all** I/O in the store. Components render `null` or a placeholder until the promise resolves.

  ```ts
  class BookStore {
    books: Book[] = []
    isLoading = false

    async fetchAll() {
      this.isLoading = true
      try {
        const data = await api.get<Book[]>("/books")
        runInAction(() => this.books = data)
      } finally {
        runInAction(() => this.isLoading = false)
      }
    }
  }
  ```
* Component pattern

  ```tsx
  const BookList = observer(() => {
    const store = useBookStore()
    useEffect(() => { store.fetchAll() }, [store])

    if (store.isLoading) return <Spinner/>
    if (store.books.length === 0) return <p>No books</p>

    return (
      <ul>
        {store.books.map(b => <li key={b.id}>{b.title}</li>)}
      </ul>
    )
  })
  ```
* Never catch and swallow errors inside the component; expose an `error` observable and render it.

## File naming conventions

* Use **PascalCase** for React components and files (e.g. `BookLibrary.tsx`).
* Hooks use **camelCase** with `use` prefix (`useReadingProgress.ts`).
* Store files end with `Store.ts` (`ReaderStore.ts`).
* Markdown, docs, and notes can use kebab or snake case if you want, but be consistent.

## Example refactors

* **Reduce props**
  Before

  ```tsx
  <BookCard
    title={book.title}
    onDelete={() => deleteBook(book.id)}
    isOpen={isSidebarOpen}
    toggleSidebar={toggleSidebar}
  />
  ```

  After

  ```tsx
  // BookCard accesses BookStore and ReaderStore directly
  const BookCard = observer(({ id }: { id: string }) => {
    const bookStore = useBookStore()
    const readerStore = useReaderStore()

    const book = bookStore.byId(id)
    const remove = () => bookStore.delete(id)

    return (
      <article>
        <h3>{book.title}</h3>
        <button onClick={remove}>Delete</button>
        <button onClick={readerStore.toggleSidebar}>Sidebar</button>
      </article>
    )
  })
  ```
* **Eliminate redundant state**

  ```tsx
  const [isMobile, setIsMobile] = useState(window.innerWidth < 1024)
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 1024)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])
  ```

  becomes (CSS handles it)

  ```tsx
  /* tailwind: lg:hidden to show mobile menu */
  ```

## Summary checklist

* Keep UI components pure and small
* Import MobX stores instead of prop drilling
* Use `useEffect` only for genuine side-effects
* Async work lives in the store; component shows loading / error states
* One component per file, PascalCase file names
* Group related components in feature folders for clarity
