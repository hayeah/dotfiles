# shortid — Short ID Generation & Prefix Resolution

Two standalone functions for human-friendly identifiers.

## `generate(existing)` — Random Short ID

Generate a unique short ID that doesn't collide with any ID in `existing`.

- **Alphabet**: `0123456789abcdefghijkmnpqrstuvwxyz` (34 chars — lowercase alphanumeric minus `o`, `i`, `l` to avoid ambiguity)
- **Length**: starts at 3 chars, grows to 8 on collision
- **Retry**: up to 10 attempts per length before growing
- **Randomness**: `secrets.token_bytes` (cryptographic)

3-char IDs give ~39k combinations. Collisions only matter after thousands of live IDs.

```python
from hayeah.core.shortid import generate

existing = {"a3f", "b7k", "c2m"}
new_id = generate(existing)  # e.g. "x9p"
```

## `resolve(query, candidates)` — Prefix Resolution

Match a query prefix against a set of candidate strings. Case-insensitive. Works with any string identifiers — short IDs, UUIDs, SHA hashes, etc.

- **Min query length**: 3 characters
- **Exact match**: returned immediately, even if it's also a prefix of another
- **Unique prefix**: returned if exactly one candidate matches
- **Ambiguous**: raises `AmbiguousIDError` listing all matches
- **No match**: raises `IDNotFoundError`

```python
from hayeah.core.shortid import resolve

sessions = ["a3f", "a3g", "b7k"]
resolve("a3f", sessions)  # "a3f" — exact match
resolve("b7k", sessions)  # "b7k"
resolve("b",   sessions)  # IDTooShortError — min 3 chars

sims = ["A1B2C3D4-E5F6-...", "A1B2C3D4-FFFF-...", "DEADBEEF-..."]
resolve("DEA", sims)         # "DEADBEEF-..."
resolve("A1B2C3D4-E", sims)  # "A1B2C3D4-E5F6-..."
resolve("A1B", sims)         # AmbiguousIDError
```

## Errors

- `IDTooShortError(ValueError)` — query shorter than 3 chars
- `AmbiguousIDError(ValueError)` — multiple candidates match the prefix
- `IDNotFoundError(ValueError)` — no candidate matches

## Test Vectors

See `libs/testdata/shortid.json`.
