# chatgpt

Available as `chatgpt` in `browser eval` scope on chatgpt.com pages.

## Routes

- `*://chatgpt.com/c/*` — conversation helpers (browser + node)
- `*://chatgpt.com/share/*` — shared link extraction (browser)
- `*://chatgpt.com/*` — common helpers (browser)

## Browser API (conversation route)

### chatgpt.messages()
Returns all conversation messages.
Returns: `Array<{id: string, role: "user" | "assistant", text: string}>`

### chatgpt.lastResponse()
Returns the text of the most recent assistant message.
Returns: `string | null`

### chatgpt.isResponseComplete()
Returns true when the assistant has finished streaming (stop button gone).
Returns: `boolean`

### chatgpt.send(text)
Types and sends a message. Sets the contenteditable prompt div and clicks send.
- `text` — the message to send

### chatgpt.title()
Returns the page title (conversation title).
Returns: `string`

## Browser API (share route)

### chatgpt.shareData()
Extracts share page data from React hydration state.
Returns: `{title: string, model: string, messages: Array<{role: string, text: string}>} | null`

## Browser API (common route)

### chatgpt.isLoggedIn()
Returns true if the user is logged in.
Returns: `boolean`

### chatgpt.currentModel()
Returns the currently selected model name.
Returns: `string | null`

## Node API (conversation route, use with `--node`)

### await chatgpt.save(path)
Extracts all messages and saves as JSON.
- `path` — output file path
Returns: `{saved: string, count: number}`

### await chatgpt.screenshot(selector, path)
Screenshots a DOM element.
- `selector` — CSS selector
- `path` — output file path
Returns: `{screenshot: string}`

## Examples

Get conversation messages:
    browser eval 'chatgpt.messages()'

Wait for messages to load:
    browser eval --expect 'result.length > 0' 'chatgpt.messages()'

Get last assistant response:
    browser eval 'chatgpt.lastResponse()'

Save conversation to file:
    browser eval --node 'await chatgpt.save("/tmp/conversation.json")'

Screenshot last message:
    browser eval --node 'await chatgpt.screenshot("[data-message-id]:last-child", "/tmp/last.png")'

Full send-and-wait workflow:
    browser eval 'chatgpt.send("Summarize this conversation")'
    browser eval --expect 'result === true' 'chatgpt.isResponseComplete()'
    browser eval 'chatgpt.lastResponse()'
