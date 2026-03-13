# Non-Interactive Fuzzy Path Matcher Spec

A deterministic, non-interactive path matcher inspired by fzf's extended-search syntax. Designed for filtering file paths programmatically — no TUI, no scoring/ranking, just boolean match/no-match.

## Reference Implementation

- **Python**: [`hayeah.fzfmatch`](https://github.com/hayeah/dotfiles/blob/master/hayeah/src/hayeah/fzfmatch.py)
- **Test vectors** (language-agnostic JSON): [`fzfmatch_testdata.json`](https://github.com/hayeah/dotfiles/blob/master/hayeah/src/hayeah/fzfmatch_testdata.json)

## Overview

The matcher operates on a list of string paths and returns the subset that satisfy a pattern expression. All matching is **case-insensitive**. Path separators are normalized to `/` before matching.

Two layers:

- **Term-level matching** — a single pattern string with space-separated terms (AND logic)
- **Expression-level composition** — combining term-level matchers with `|` (AND/intersect) and `;` (OR/union)

## Design Decisions

- **No scoring/ranking** — pure boolean filter. Returns matches in input order.
- **Word boundary** — Unicode letter or digit are word chars. Underscore is NOT a word char (unlike regex `\w`). `_` acts as a boundary.
- **`./` as `^`** — convenience for relative path patterns. `./render` is equivalent to `^render`.
- **Operator precedence** — `|` splits first (lower precedence), `;` binds tighter (higher precedence). So `a;b | c` parses as `(a OR b) AND c`.
- **No glob/regex** — all matching is literal substring with optional modifiers. Simple and portable.

---

## Term-Level Matching

A pattern string is split on whitespace into **terms**. A path matches only if **every term** matches (implicit AND).

### Term Syntax

Each term is parsed left-to-right for modifier prefixes/suffixes:

```
[!]['][^]<text>[$][']
```

Parsing order:

- `!` — negation (checked first, stripped)
- `'...'` or `'...` — word boundary modifiers (checked next, stripped)
- `./` — treated as `^` anchor (stripped)
- `^` — head anchor (prefix match)
- `$` — tail anchor (suffix match)

After stripping modifiers, the remaining `<text>` is lowercased and used for matching. Empty `<text>` after stripping is an error.

### Modifiers

| Modifier | Syntax | Meaning |
|---|---|---|
| Substring | `foo` | Path contains "foo" |
| Head anchor | `^foo` | Path starts with "foo" |
| Tail anchor | `foo$` | Path ends with "foo" |
| Exact path | `^foo$` | Path equals "foo" exactly |
| Word prefix | `'foo` | "foo" at a word boundary start (left side) |
| Word exact | `'foo'` | "foo" bounded on both sides by word boundaries |
| Negation | `!foo` | Path does NOT contain "foo" |
| Dir anchor | `./foo` | Equivalent to `^foo` |

Negation composes with other modifiers: `!'test'`, `!^cmd`, `!.go$`.

### Word Boundary Definition

A **word boundary** exists at:
- Start or end of the string
- Any position adjacent to a **non-word character**

A **word character** is: Unicode letter or Unicode digit.

Note: `_` is **not** a word character (unlike regex `\w`).

### Match Algorithm

```
function termMatches(term, path):
  // Fast path: exact match
  if term.anchorHead AND term.anchorTail AND NOT (term.wordExact OR term.wordPrefix):
    return path == term.text

  // Check anchors
  sub = path
  if term.anchorHead:
    if NOT path.startsWith(term.text): return false
    sub = path[0:len(term.text)]
  if term.anchorTail:
    if NOT path.endsWith(term.text): return false
    sub = path[len(path)-len(term.text):]

  // Check word boundaries or substring
  if term.wordExact:
    return containsWordExact(sub, term.text)
  else if term.wordPrefix:
    return containsWordPrefix(sub, term.text)
  else:
    return sub.contains(term.text)
```

**containsWordExact(s, needle):** Find all occurrences of `needle` in `s`. Return true if any occurrence has word boundaries on **both** sides.

**containsWordPrefix(s, needle):** Find all occurrences of `needle` in `s`. Return true if any occurrence has a word boundary on the **left** side.

For negated terms, invert the final boolean result.

### Full Term Matching

```
function match(pattern, paths):
  terms = parseTerms(pattern)
  if terms is empty: return paths    // empty pattern matches all

  result = []
  for path in paths:
    normal = lowercase(toSlash(path))
    allMatch = true
    for term in terms:
      m = termMatches(term, normal)
      if term.neg: m = NOT m
      if NOT m:
        allMatch = false
        break
    if allMatch:
      result.append(path)            // return original path
  return result
```

---

## Expression-Level Composition

Patterns can be composed using two operators. These operate on the results of term-level matchers.

### Operators

| Operator | Symbol | Meaning | Precedence |
|---|---|---|---|
| Intersect (AND) | `\|` (pipe) | Results must satisfy ALL sub-patterns | Lower (splits first) |
| Union (OR) | `;` (semicolon) | Results from ANY sub-pattern | Higher (binds tighter) |

### Parsing Rules

- Check for `|` first. If present, split on `|` — each part is recursively parsed, results are intersected (CompoundMatcher).
- If no `|`, check for `;`. If present, split on `;` — each part is recursively parsed, results are unioned (UnionMatcher).
- If neither, the expression is a plain term-level pattern (FuzzyMatcher).
- Empty parts after splitting are skipped. Parts are trimmed.

### Precedence Example

```
"cmd/vibe .go;render .go | !test"
```

Splits on `|` first:
- `"cmd/vibe .go;render .go"` — contains `;`, becomes Union of:
  - `"cmd/vibe .go"` — paths containing "cmd/vibe" AND ".go"
  - `"render .go"` — paths containing "render" AND ".go"
- `"!test"` — paths NOT containing "test"

Result: `((cmd/vibe AND .go) OR (render AND .go)) AND (NOT test)`

### Composition Algorithm

```
function parseMatcher(pattern):
  pattern = trim(pattern)

  if pattern contains "|":
    parts = split(pattern, "|")
    matchers = [parseMatcher(trim(p)) for p in parts if trim(p) != ""]
    return CompoundMatcher(matchers)

  if pattern contains ";":
    parts = split(pattern, ";")
    matchers = [parseMatcher(trim(p)) for p in parts if trim(p) != ""]
    return UnionMatcher(matchers)

  return FuzzyMatcher(pattern)

// CompoundMatcher: pipe output of each matcher into the next
function compoundMatch(matchers, paths):
  current = paths
  for m in matchers:
    current = m.match(current)
  return current

// UnionMatcher: collect all results, deduplicated
function unionMatch(matchers, paths):
  resultSet = {}
  for m in matchers:
    resultSet.addAll(m.match(paths))
  return resultSet.values()
```

---

## Multi-Line Pattern Lists

Multiple patterns can be provided as a newline-separated list. Each line produces an independent matcher.

```
cmd/.go
internal/.go

# comments start with #
```

- Empty lines are skipped
- Lines starting with `#` are comments (skipped)
- Each line is parsed via `parseMatcher()`

---

## Error Conditions

The parser must reject and return an error for:

- Empty term after stripping modifiers: `^`, `$`, `!`, `'`, `''`
- Empty text after negation: `!`
- Empty text after leading quote: `'`

---

## Test Vectors

### Term-Level

| Pattern | Input | Matches? | Notes |
|---|---|---|---|
| `cmd` | `cmd/vibe/select.go` | yes | substring |
| `cmd .go` | `cmd/vibe/select.go` | yes | both terms match |
| `cmd .go` | `docs/intro.txt` | no | "cmd" not found |
| `^cmd` | `cmd/vibe/select.go` | yes | prefix |
| `^cmd` | `internal/cmd/foo.go` | no | not prefix |
| `.go$` | `cmd/vibe/select.go` | yes | suffix |
| `.go$` | `README.md` | no | not suffix |
| `^README.md$` | `README.md` | yes | exact |
| `^README.md$` | `docs/README.md` | no | not exact |
| `'select` | `cmd/vibe/select.go` | yes | `/` is boundary |
| `'select` | `cmd/vibe/unselect.go` | no | no left boundary |
| `'select'` | `cmd/vibe/select.go` | yes | `/` and `.` are boundaries |
| `'select'` | `cmd/vibe/selected.go` | no | no right boundary |
| `!select` | `cmd/vibe/ask.go` | yes | negation |
| `!select` | `cmd/vibe/select.go` | no | negation |
| `readme` | `README.md` | yes | case-insensitive |
| `./render` | `render/foo.go` | yes | ./ as ^ anchor |
| `./render` | `cmd/render/bar.go` | no | not prefix |

### Word Boundary Edge Cases

| String | Needle | `containsWordExact`? | Notes |
|---|---|---|---|
| `pre_test` | `test` | yes | `_` is NOT a word char |
| `pre2test` | `test` | no | `2` IS a word char |
| `unselected` | `select` | no | both sides are word chars |
| `test-string` | `string` | yes | `-` is a boundary |
| `pre-test` | `test` | yes | `-` is a boundary |

### Expression-Level

| Pattern | Input Paths | Result |
|---|---|---|
| `foo;bar` | `[src/foo.go, docs/bar.md, main.go]` | `[src/foo.go, docs/bar.md]` |
| `cmd/vibe .go \| !test` | `[cmd/vibe/foo.go, cmd/vibe/foo_test.go]` | `[cmd/vibe/foo.go]` |
| `cmd .go;render .go \| !test` | `[cmd/a.go, cmd/a_test.go, render/b.go, render/b_test.go]` | `[cmd/a.go, render/b.go]` |
| `""` (empty) | any paths | all paths returned |
