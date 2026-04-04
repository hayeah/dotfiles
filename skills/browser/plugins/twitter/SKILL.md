# twitter

Browser plugin for extracting tweets from Twitter/X pages. Auto-loaded on `x.com` and `twitter.com`.

## Routes

- `*://x.com/i/lists/*` — list timelines (browser + node)
- `*://x.com/*/status/*` — tweet threads (browser + node)
- `*://x.com/*` — any X page (browser + node)

## How Scrolling Works

Twitter uses a **virtual DOM** — it replaces tweet articles as you scroll, keeping only ~10–15 tweets in the DOM at a time. The `twitter.fetch()` (node) function handles this by scrolling incrementally and collecting unique tweet IDs into a Map before they scroll out of view.

The scroll container is `window` (not a nested div), so `window.scrollBy()` is used.

## Browser API

Available as `twitter` in `browser eval` scope on x.com pages.

### twitter.tweets()
Extract all currently visible tweets from the DOM.
Returns: `Array<Tweet>`

```
Tweet = {
  id: string,           // tweet ID (numeric string)
  author: string,       // @handle without the @
  displayName: string,  // display name
  text: string,         // tweet text content
  time: string,         // ISO 8601 datetime
  url: string,          // canonical tweet URL
  retweet: string|null, // retweet attribution text, or null
  images: string[],     // pbs.twimg.com/media URLs
}
```

### twitter.visibleIds()
Returns IDs of all currently visible tweets.
Returns: `string[]`

### twitter.scrollDown(amount?)
Scroll down by `amount` pixels (default: `window.innerHeight`).
Returns: `number` (new scrollY)

### twitter.scrollTo(y)
Scroll to absolute position `y`.

### twitter.scrollState()
Returns: `{ scrollY: number, scrollHeight: number, atBottom: boolean }`

### twitter.isListPage()
Returns: `boolean`

### twitter.pageTitle()
Returns: `string`

## Node API (use with `--node`)

### await twitter.fetch(options?)
Scroll through the page and collect tweets, handling virtual DOM turnover.

Options:
- `limit` — max tweets to collect (default: 100)
- `until` — ISO date string; stop when oldest tweet is before this date
- `delay` — ms to wait after each scroll (default: 1500)
- `scrollAmount` — pixels per scroll step (default: window.innerHeight)
- `maxStalls` — stop after this many scrolls with no new tweets (default: 5)
- `verbose` — log progress to stderr (default: false)

Returns: `{ tweets: Tweet[], scrollCount: number, stoppedReason: "limit"|"until"|"bottom"|"stalled" }`

### await twitter.save(path, options?)
Like `fetch()` but saves tweets as JSON to `path`.
Returns: `{ saved: string, count: number, scrollCount: number, stoppedReason: string }`

### await twitter.fetchMarkdown(options?)
Like `fetch()` but returns tweets formatted as a markdown string.
Returns: `string`

## Examples

Get currently visible tweets (browser):

    browser eval 'JSON.stringify(twitter.tweets())'

Scroll through a list and save 50 tweets to JSON:

    browser eval --node 'return JSON.stringify(await twitter.save("/tmp/tweets.json", {limit: 50, verbose: true}))'

Get tweets as markdown (pipe to file):

    browser eval --node 'return await twitter.fetchMarkdown({limit: 30})' > tweets.md

Collect tweets newer than a date:

    browser eval --node 'return JSON.stringify(await twitter.fetch({until: "2026-03-30T00:00:00Z", limit: 200}))'

Check scroll state:

    browser eval 'JSON.stringify(twitter.scrollState())'
