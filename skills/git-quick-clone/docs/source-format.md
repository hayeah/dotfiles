# Git Source Format Spec

A language-agnostic specification for parsing git repository references into structured clone information.

## Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Clone URL, always `.git`-suffixed |
| `repo_id` | string | Canonical identifier: `{host}/{user}/{repo}` (no `.git` suffix) |
| `user` | string | Repository owner / organization |
| `repo` | string | Repository name (no `.git` suffix) |
| `branch` | string? | Branch name, extracted from tree/blob URLs |
| `sparse_path` | string? | Subdirectory for sparse checkout |

## Input Formats

### Shorthand — `user/repo`

Bare `user/repo` without any URL scheme or `@` prefix. Assumes GitHub.

- Must contain exactly one `/`
- Multi-level paths (`org/user/repo`) are invalid
- Clone URL: `https://github.com/{user}/{repo}.git`
- Repo ID: `github.com/{user}/{repo}`
- Repo names may contain dots, dashes, underscores (e.g. `complex-repo-name.js`)

### Domain-Prefixed Shorthand — `github.com/user/repo`

Input starting with a known host (`github.com`, `gitlab.com`) followed by `/`.

- Treated as HTTPS: prepend `https://` and parse as HTTPS URL

### HTTPS URL — `https://github.com/user/repo`

Standard HTTPS clone URL.

- Host must be a known host (`github.com`, `gitlab.com`)
- `.git` suffix on the repo name is optional and stripped from `repo` and `dest_dir`
- Query parameters (e.g. `?tab=readme-ov-file`) are silently ignored
- Clone URL reconstructed as `https://{host}/{user}/{repo}.git` (query params dropped)

### HTTPS Tree URL — `https://github.com/user/repo/tree/{branch}[/{path}]`

GitHub/GitLab URL pointing at a directory within a branch.

- `branch` is extracted from the path segment after `tree/`
- If additional path segments follow the branch, they are joined as `sparse_path`
- If no path follows the branch, `sparse_path` is `null`

### HTTPS Blob URL — `https://github.com/user/repo/blob/{branch}/{path}`

GitHub/GitLab URL pointing at a specific file.

- `branch` is extracted from the path segment after `blob/`
- `sparse_path` is the **containing directory** of the file (not the file itself)
  - For `blob/main/README.md` → `sparse_path` is `""` (root)
  - For `blob/main/docs/guide.md` → `sparse_path` is `"docs"`
  - For `blob/main/a/b/c.txt` → `sparse_path` is `"a/b"`

### SSH URL — `git@{host}:user/repo[.git]`

Standard git SSH clone URL.

- Host must match a known host
- `.git` suffix is optional and stripped from `repo` and `dest_dir`
- Clone URL: `git@{host}:{user}/{repo}.git`

## Post-Processing Rules

Applied to all formats after initial parsing:

- If `url` does not end with `.git`, append `.git`
- If `repo_id` ends with `.git`, strip it

## Known Hosts

- `github.com`
- `gitlab.com`

## Error Cases

| Input | Error |
|-------|-------|
| `org/user/repo` | Shorthand with more than one `/` |
| `invalid-url-format` | No scheme, no `/` — unrecognized format |
| `https://bitbucket.org/user/repo` | Unsupported host |
| Malformed SSH URL | Cannot extract user/repo |

## Test Cases

See [`test_cases.json`](test_cases.json) for the canonical set of test cases.
