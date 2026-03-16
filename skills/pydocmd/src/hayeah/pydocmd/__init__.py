"""Extract Python public API as markdown from source files using AST.

Parses Python source statically (no imports needed) and emits markdown
with class/function signatures and their docstrings. Skips private members.

Quick start:
    from hayeah.pydocmd import extract_module_api, render_markdown
    api = extract_module_api(Path("some_module.py"))
    print(render_markdown(api))
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParamInfo:
    """A single function/method parameter."""

    name: str
    annotation: str | None = None
    default: str | None = None
    kind: str = "regular"  # "regular", "keyword_only", "positional_only"


@dataclass
class FuncInfo:
    """A function or method with its signature and docstring."""

    name: str
    params: list[ParamInfo] = field(default_factory=list)
    return_annotation: str | None = None
    docstring: str | None = None
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False


@dataclass
class ClassInfo:
    """A class with its docstring and public methods."""

    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str | None = None
    methods: list[FuncInfo] = field(default_factory=list)


@dataclass
class ModuleAPI:
    """The public API surface of a module."""

    path: Path
    module_name: str = ""
    module_docstring: str | None = None
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FuncInfo] = field(default_factory=list)
    constants: list[tuple[str, str]] = field(default_factory=list)  # (name, annotation_or_value)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _unparse_safe(node: ast.expr) -> str:
    return ast.unparse(node)


def _extract_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParamInfo]:
    params: list[ParamInfo] = []
    args = func.args

    for i, arg in enumerate(args.posonlyargs):
        default = None
        defaults_offset = len(args.defaults) - len(args.posonlyargs) - len(args.args)
        di = defaults_offset + i
        if 0 <= di < len(args.defaults):
            default = _unparse_safe(args.defaults[di])
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_unparse_safe(arg.annotation) if arg.annotation else None,
            default=default,
            kind="positional_only",
        ))

    for i, arg in enumerate(args.args):
        default = None
        di = i - (len(args.args) - len(args.defaults))
        if 0 <= di < len(args.defaults):
            default = _unparse_safe(args.defaults[di])
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_unparse_safe(arg.annotation) if arg.annotation else None,
            default=default,
        ))

    if args.vararg:
        params.append(ParamInfo(
            name=f"*{args.vararg.arg}",
            annotation=_unparse_safe(args.vararg.annotation) if args.vararg.annotation else None,
        ))
    elif args.kwonlyargs:
        params.append(ParamInfo(name="*"))

    for i, arg in enumerate(args.kwonlyargs):
        default = None
        if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
            default = _unparse_safe(args.kw_defaults[i])
        params.append(ParamInfo(
            name=arg.arg,
            annotation=_unparse_safe(arg.annotation) if arg.annotation else None,
            default=default,
            kind="keyword_only",
        ))

    if args.kwarg:
        params.append(ParamInfo(
            name=f"**{args.kwarg.arg}",
            annotation=_unparse_safe(args.kwarg.annotation) if args.kwarg.annotation else None,
        ))

    return params


def _has_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == name:
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == name:
            return True
    return False


def _extract_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncInfo:
    params = _extract_params(node)
    return FuncInfo(
        name=node.name,
        params=params,
        return_annotation=_unparse_safe(node.returns) if node.returns else None,
        docstring=ast.get_docstring(node),
        is_static=_has_decorator(node, "staticmethod"),
        is_classmethod=_has_decorator(node, "classmethod"),
        is_property=_has_decorator(node, "property"),
    )


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _extract_dunder_all(tree: ast.Module) -> set[str] | None:
    """Extract __all__ from a module AST, if defined."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return {
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
    return None


# ---------------------------------------------------------------------------
# Module name derivation
# ---------------------------------------------------------------------------


def module_name_from_path(path: Path) -> str:
    """Derive a dotted module name from a file path.

    Looks for a ``src/`` directory in the path and uses everything after it.
    Falls back to the filename stem if no ``src/`` is found.

    Examples:
        src/hayeah/imagegen/__init__.py → hayeah.imagegen
        src/hayeah/imagegen/openai.py  → hayeah.imagegen.openai
        foo/bar.py                     → bar
    """
    parts = path.parts
    try:
        src_idx = len(parts) - 1 - list(reversed(parts)).index("src")
        module_parts = list(parts[src_idx + 1 :])
    except ValueError:
        module_parts = [path.stem]
        return ".".join(module_parts)

    # Strip .py extension from last part
    last = module_parts[-1]
    if last.endswith(".py"):
        module_parts[-1] = last[:-3]

    # __init__ → use parent package name
    if module_parts[-1] == "__init__":
        module_parts.pop()

    return ".".join(module_parts)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_module_api(path: Path) -> ModuleAPI:
    """Parse a Python source file and extract the public API surface.

    If the module defines ``__all__``, only those names are included.
    Otherwise falls back to all non-underscore names.
    """
    source = path.read_text()
    tree = ast.parse(source)

    dunder_all = _extract_dunder_all(tree)

    def _is_exported(name: str) -> bool:
        if dunder_all is not None:
            return name in dunder_all
        return _is_public(name)

    api = ModuleAPI(
        path=path,
        module_name=module_name_from_path(path),
        module_docstring=ast.get_docstring(tree),
    )

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and _is_exported(node.name):
            class_info = ClassInfo(
                name=node.name,
                bases=[_unparse_safe(b) for b in node.bases],
                docstring=ast.get_docstring(node),
            )
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _is_public(item.name) or item.name == "__init__":
                        func = _extract_func(item)
                        class_info.methods.append(func)
            api.classes.append(class_info)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_exported(node.name):
            func = _extract_func(node)
            if func.docstring:
                api.functions.append(func)

        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if _is_exported(name):
                ann = _unparse_safe(node.annotation)
                api.constants.append((name, ann))

    return api


# ---------------------------------------------------------------------------
# Signature formatting
# ---------------------------------------------------------------------------

# Max line length before we switch to multi-line signature
_MAX_SIG_LINE = 80


def _format_param(p: ParamInfo) -> str:
    if p.name in ("*", "/"):
        return p.name

    parts = [p.name]
    if p.annotation:
        parts.append(f": {p.annotation}")
    if p.default is not None:
        if p.annotation:
            parts.append(f" = {p.default}")
        else:
            parts.append(f"={p.default}")
    return "".join(parts)


def _format_signature(func: FuncInfo, skip_self: bool = False) -> str:
    """Format a function signature, using multi-line if it's long."""
    params = func.params
    if skip_self and params and params[0].name in ("self", "cls"):
        params = params[1:]

    param_strs = [_format_param(p) for p in params]
    ret = f" -> {func.return_annotation}" if func.return_annotation else ""

    # Try single-line first
    inline = f"def {func.name}({', '.join(param_strs)}){ret}"
    if len(inline) <= _MAX_SIG_LINE:
        return inline

    # Multi-line
    lines = [f"def {func.name}("]
    for i, ps in enumerate(param_strs):
        comma = "," if i < len(param_strs) - 1 else ","
        lines.append(f"    {ps}{comma}")
    lines.append(f"){ret}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Docstring reformatting
# ---------------------------------------------------------------------------

# Google-style section headers
_SECTION_RE = re.compile(r"^(Args|Arguments|Returns|Return|Raises|Attributes|Note|Notes|Example|Examples|Yields|Yield):\s*$")
# Arg line: "    name: description" or "    name (type): description"
_ARG_RE = re.compile(r"^(\w+)(?:\s*\([^)]*\))?\s*[:—–-]\s*(.*)$")


def _reformat_docstring(docstring: str) -> str:
    """Reformat a Google-style docstring into proper markdown.

    Converts:
    - Args/Attributes/Raises sections → **Section:** with `- name` list items
    - Returns section → **Returns:** with body text
    - Plain paragraphs → passed through
    """
    text = textwrap.dedent(docstring).strip()
    lines = text.split("\n")

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        section_match = _SECTION_RE.match(line.strip())

        if section_match:
            section_name = section_match.group(1)
            out.append(f"**{section_name}:**")
            i += 1

            if section_name in ("Args", "Arguments", "Attributes", "Raises"):
                # Parse as definition list → markdown bullet list
                while i < len(lines):
                    stripped = lines[i]
                    # Detect end of section: blank line followed by non-indented text,
                    # or another section header
                    if stripped.strip() == "":
                        # Peek ahead: if next non-blank line is not indented, end section
                        j = i + 1
                        while j < len(lines) and lines[j].strip() == "":
                            j += 1
                        if j >= len(lines) or not lines[j].startswith(" "):
                            break
                        i += 1
                        continue

                    if not stripped.startswith(" "):
                        break

                    content = stripped.strip()
                    arg_match = _ARG_RE.match(content)
                    if arg_match:
                        name, desc = arg_match.group(1), arg_match.group(2)
                        # Collect continuation lines (more indented than the arg name)
                        indent_len = len(stripped) - len(stripped.lstrip())
                        i += 1
                        while i < len(lines):
                            next_line = lines[i]
                            if next_line.strip() == "":
                                break
                            next_indent = len(next_line) - len(next_line.lstrip())
                            if next_indent <= indent_len:
                                break
                            desc += " " + next_line.strip()
                            i += 1
                        out.append(f"- `{name}` — {desc}")
                    else:
                        out.append(f"  {content}")
                        i += 1
                out.append("")
            else:
                # Returns, Note, Example, etc. — just collect body text
                body_lines: list[str] = []
                while i < len(lines):
                    if lines[i].strip() == "" and i + 1 < len(lines) and not lines[i + 1].startswith(" "):
                        break
                    if not lines[i].startswith(" ") and lines[i].strip() != "" and _SECTION_RE.match(lines[i].strip()):
                        break
                    body_lines.append(lines[i].strip())
                    i += 1
                body = " ".join(bl for bl in body_lines if bl)
                if body:
                    out.append(body)
                out.append("")
        elif line.startswith("    "):
            # Indented block — collect lines
            block_lines: list[str] = []
            while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
                # Stop on blank line followed by non-indented text
                if lines[i].strip() == "":
                    j = i + 1
                    while j < len(lines) and lines[j].strip() == "":
                        j += 1
                    if j >= len(lines) or not lines[j].startswith("    "):
                        break
                block_lines.append(lines[i][4:])  # strip 4-space indent
                i += 1
            # Strip trailing blank lines
            while block_lines and block_lines[-1].strip() == "":
                block_lines.pop()
            # Heuristic: if most non-blank lines start with - or *, it's a list, not code
            non_blank = [bl for bl in block_lines if bl.strip()]
            is_list = non_blank and all(bl.lstrip().startswith(("- ", "* ")) for bl in non_blank)
            if is_list:
                out.extend(block_lines)
            else:
                out.append("```python")
                out.extend(block_lines)
                out.append("```")

        else:
            out.append(line)
            i += 1

    return "\n".join(out).rstrip()


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(api: ModuleAPI, heading_level: int = 2) -> str:
    """Render a ModuleAPI as markdown.

    Headings use dotted paths. Methods use # for instance, . for static/class.
    Signatures are in ```python code blocks.
    """
    h = "#" * heading_level
    h1 = "#" * (heading_level + 1)
    mod = api.module_name
    lines: list[str] = []

    if api.module_docstring:
        lines.append(_reformat_docstring(api.module_docstring))
        lines.append("")

    # Constants
    if api.constants:
        for name, ann in api.constants:
            lines.append(f"- `{name}: {ann}`")
        lines.append("")

    # Functions
    for func in api.functions:
        qual = f"{mod}.{func.name}" if mod else func.name
        lines.append(f"{h} {qual}")
        lines.append("")
        sig = _format_signature(func)
        lines.append(f"```python\n{sig}\n```")
        lines.append("")
        if func.docstring:
            lines.append(_reformat_docstring(func.docstring))
            lines.append("")

    # Classes
    for cls in api.classes:
        qual = f"{mod}.{cls.name}" if mod else cls.name
        base_str = f"({', '.join(cls.bases)})" if cls.bases else ""
        lines.append(f"{h} {qual}{base_str}")
        lines.append("")
        if cls.docstring:
            lines.append(_reformat_docstring(cls.docstring))
            lines.append("")

        for method in cls.methods:
            # Heading: Class#method for instance, Class.method for static/classmethod
            if method.is_static or method.is_classmethod:
                sep = "."
            else:
                sep = "#"

            label = method.name
            if method.name == "__init__":
                label = "constructor"

            if method.is_property:
                lines.append(f"{h1} {cls.name}{sep}{label} (property)")
            else:
                tag = ""
                if method.is_static:
                    tag = " `@staticmethod`"
                elif method.is_classmethod:
                    tag = " `@classmethod`"
                lines.append(f"{h1} {cls.name}{sep}{label}{tag}")

            lines.append("")

            if not method.is_property:
                sig = _format_signature(method, skip_self=True)
                lines.append(f"```python\n{sig}\n```")
                lines.append("")

            if method.docstring:
                lines.append(_reformat_docstring(method.docstring))
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"
