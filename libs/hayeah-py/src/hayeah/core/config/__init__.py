"""hayeah.core.config — single-envar config loading.

One env var per app (``<APP>_CONFIG``). Value is either a file path
(``.json`` / ``.toml``, detected by extension) or a JSON literal.

Examples::

    # plain dict
    raw = load("MY_APP_CONFIG")

    # typed dataclass
    cfg = load("MY_APP_CONFIG", into=AppConfig)
"""

from __future__ import annotations

import dataclasses
import json
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
    """Load config from the env var *env_var*.

    The value is interpreted as:
    - File path ending ``.toml`` → load as TOML
    - File path ending ``.json`` → load as JSON
    - Anything else → parse as JSON literal

    Returns an empty dict (or default-constructed *into*) when the env var
    is unset or empty. Returns empty when a file path doesn't exist.
    """
    value = os.getenv(env_var)
    raw: dict = {}

    if value:
        if value.endswith(".toml"):
            p = Path(value).expanduser()
            if p.is_file():
                with open(p, "rb") as f:
                    raw = tomllib.load(f)
        elif value.endswith(".json"):
            p = Path(value).expanduser()
            if p.is_file():
                raw = json.loads(p.read_text())
        else:
            raw = json.loads(value)

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
