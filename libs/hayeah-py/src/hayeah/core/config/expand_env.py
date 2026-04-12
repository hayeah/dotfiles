"""Env var interpolation for config string values.

Syntax:
    ${VAR}            -> os.environ["VAR"], or "" if missing
    ${VAR:-default}   -> os.environ["VAR"] if set and non-empty, else default
    $$                -> literal "$"

Bare ``$`` (not followed by ``{``) is left as-is. Single-pass: the result of
one substitution is not re-scanned.
"""

from __future__ import annotations

import os
import re

_INTERP_RE = re.compile(r"\$\$|\$\{([^}]+)\}")


def expand_env(value: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        if m.group(0) == "$$":
            return "$"
        expr = m.group(1)
        if ":-" in expr:
            key, default = expr.split(":-", 1)
            return os.environ.get(key) or default
        return os.environ.get(expr, "")

    return _INTERP_RE.sub(_replace, value)
