"""hayeah.config — load a TOML config file from an env-var path.

Point an environment variable at a TOML file; ``load()`` reads and returns it
as a plain dict or a typed dataclass.

Examples::

    # plain dict
    raw = load("HAYEAH_CONFIG")

    # typed dataclass
    cfg = load("HAYEAH_CONFIG", into=AppConfig)
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, TypeVar, overload

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

T = TypeVar("T")


@overload
def load(env_var: str) -> dict: ...


@overload
def load(env_var: str, *, into: type[T]) -> T: ...


def load(env_var: str, *, into: type[T] | None = None) -> dict | T:
    """Load a TOML config file from the path in *env_var*.

    Returns an empty dict (or default-constructed *into*) when the env var
    is unset or the file is missing.
    """
    config_path = os.getenv(env_var)
    raw: dict = {}

    if config_path:
        p = Path(config_path).expanduser()
        if p.is_file():
            with open(p, "rb") as f:
                raw = tomllib.load(f)

    if into is not None:
        return _from_dict(into, raw)
    return raw


def _from_dict(cls: type[T], raw: dict) -> T:
    """Recursively construct a dataclass from a dict."""
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls} is not a dataclass")

    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in raw:
            continue
        kwargs[f.name] = _coerce(f.type, raw[f.name])
    return cls(**kwargs)


def _coerce(type_hint: Any, value: Any) -> Any:
    """Coerce a TOML value to match a dataclass field type."""
    # Resolve string annotations
    if isinstance(type_hint, str):
        type_hint = _resolve_type(type_hint)

    origin = getattr(type_hint, "__origin__", None)

    # Union types (X | None) — try the non-None branch
    if _is_union(type_hint):
        args = [a for a in type_hint.__args__ if a is not type(None)]
        if value is None:
            return None
        if args:
            return _coerce(args[0], value)
        return value

    # Nested dataclass
    if dataclasses.is_dataclass(type_hint) and isinstance(value, dict):
        return _from_dict(type_hint, value)

    # Path — expand ~
    if type_hint is Path:
        return Path(value).expanduser()

    return value


def _is_union(tp: Any) -> bool:
    import types
    import typing

    return isinstance(tp, types.UnionType) or getattr(tp, "__origin__", None) is typing.Union


def _resolve_type(hint: str) -> Any:
    """Resolve common string type annotations."""
    import types

    hint = hint.strip()
    if "|" in hint:
        parts = [_resolve_type(p) for p in hint.split("|")]
        result = parts[0]
        for p in parts[1:]:
            result = result | p
        return result
    simple = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "None": type(None),
        "Path": Path,
    }
    return simple.get(hint, str)
