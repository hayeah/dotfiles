---
name: python
description: Coding convention, style guide, and tooling for writing Python.
---

# Python Project

Project setup

- use uv with pyproject.toml
- define both project and project.scripts
- proper src structure for internal package imports
- .gitignore: https://raw.githubusercontent.com/github/gitignore/master/Python.gitignore

Code quality
- ruff for autoformat
- pyright for type checking
- pytest for unit tests
	- put test files beside the source file
	- foo.py should have foo_test.py

CLI tools

- use typer for the cli main script
- install with `uv tool install -e .`
- for complex output, prefer output in JSON.

## Python coding style

* Code structure
	* When writing a fairly complex feature, avoid having a "bag of loose functions" that call each other and pass parameters around.
	* Group related methods together in a class.
	* Group common data as properties of a class instead of using parameters to pass state around.
	* Use type annotations and dataclasses.
	* Use a simple dependency injection style similar to Go's "wire" system.
	  * Avoid deep, recursive initializations.
	  * Prefer factory functions or class constructors that build an acyclic dependency graph to produce the final object.

* Error handling and cleanup
	* Avoid `try ... except` unless you have good reasons.
	* It is fine to fail fast: let the error raise and the app crash, rather than adding a `try ... except` just to wrap or re-report it.
	* Prefer using `with` statements to handle cleanup.
	* Use `try ... except` if:
	  * You have a clear recovery strategy.
	  * The code runs in a loop and you want to keep going after individual failures.

* Loops and helper functions
	* If you are writing a loop and the loop body is complicated, extract a helper function or method that encapsulates the processing for a single item.

* Naming and file layout
    * Function naming:
      * Avoid the `get_` prefix for data-oriented functions.
      * Prefer a bare `noun` (preferred), or `imperativeverb_noun`.
    * File naming conventions:
      * Put test files beside the source file.
      * `foo.py` should have `foo_test.py`.
      * If asked to write Markdown documentation for `foo.py`, write it in `foo.md`.

  * Testing (pytest)
    * For tests that have varied and clear input/output expectations, use data-driven tests to reduce code redundancy.

* Dataclasses and JSON serialization
  * For dataclasses that require JSON serialization, define and use this mixin:

```python
class JsonMixin:
    """Mixin to add JSON serialization to dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """
        Return a JSON-serializable dict representation.

        For dataclasses, this uses dataclasses.asdict, which also
        recursively converts nested dataclasses.
        """
        if is_dataclass(self):
            return asdict(self)
        # Fallback if you ever use this on a non-dataclass
        return self.__dict__

    def to_json(self, **json_kwargs: Any) -> str:
        """
        Return a JSON string representation.

        Extra keyword args are passed through to json.dumps
        (e.g. indent=2, sort_keys=True).
        """
        return json.dumps(self.to_dict(), **json_kwargs)
```

## Terminal Output

Use `rich` if rich terminal output is called for:

https://github.com/Textualize/rich

## Makefile.py

See [pymake](./pymake.md) for a detailed example of creating a Makefile.py for project build tasks. You MUST read this documentation when you first create Makefile.py.

```py
"""Makefile.py for pymake project."""

from pymake import sh, task

@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/pymake")


@task()
def typecheck():
    """Run mypy type checker."""
    sh("mypy src/pymake")
```

## Python Notebook

If you are working on a Jupyter notebook, you MUST read [./notebook.md](./notebook.md).

## Logging

Use stdlib logging for logs. Set it up using the following snippet:

```py
import logging
import os
import sys
from pathlib import Path


def _parse_level(s: str | None) -> int:
    if not s:
        return logging.INFO
    s = s.strip()
    if s.isdigit():
        return int(s)
    return getattr(logging, s.upper(), logging.INFO)


class NamePrefixAllowFilter(logging.Filter):
    """
    Allow only records whose logger name matches one of the prefixes.
    A prefix "myapp" allows "myapp" and "myapp.*".
    """
    def __init__(self, prefixes: list[str]):
        super().__init__()
        self.prefixes = [p for p in (prefixes or []) if p]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.prefixes:
            return True
        name = record.name
        for p in self.prefixes:
            if name == p or name.startswith(p + "."):
                return True
        return False


def setup_logging() -> None:
    level = _parse_level(os.getenv("LOG_LEVEL", "INFO"))

    raw_filter = (os.getenv("LOG_FILTER") or "").strip()
    prefixes = [x.strip() for x in raw_filter.split(",") if x.strip()] if raw_filter else []

    output = (os.getenv("LOG_OUTPUT") or "stderr").strip()

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate logs if setup_logging() is called multiple times
    for h in list(root.handlers):
        root.removeHandler(h)

    if output.lower() in ("stdout", "out"):
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
    elif output.lower() in ("stderr", "err", ""):
        handler = logging.StreamHandler(sys.stderr)
    else:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")

    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    if prefixes:
        handler.addFilter(NamePrefixAllowFilter(prefixes))

    root.addHandler(handler)


if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("hello")
```

