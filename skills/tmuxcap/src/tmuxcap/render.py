"""Render ANSI text to various output formats."""

import io
from dataclasses import dataclass

from rich.console import Console
from rich.text import Text


@dataclass
class ANSIRenderer:
    """Renders ANSI text to markdown, HTML, SVG, or image formats."""

    ansi_text: str
    width: int = 200

    @property
    def parsed(self) -> Text:
        return Text.from_ansi(self.ansi_text)

    def _console(self) -> Console:
        c = Console(record=True, width=self.width, file=io.StringIO())
        c.print(self.parsed, end="")
        return c

    def plain(self) -> str:
        return self.parsed.plain

    def html(self) -> str:
        return self._console().export_html()

    def svg(self) -> str:
        return self._console().export_svg()

    def image(self, fmt: str = "png") -> bytes:
        from PIL import Image, ImageDraw, ImageFont

        console = Console(width=self.width, file=io.StringIO())
        segments = list(console.render(self.parsed))

        bg_default = (30, 30, 30)
        fg_default = (204, 204, 204)

        # Build grid of (char, fg, bg)
        grid: list[list[tuple[str, tuple[int, int, int], tuple[int, int, int]]]] = []
        current_line: list[tuple[str, tuple[int, int, int], tuple[int, int, int]]] = []
        for seg in segments:
            if seg.control:
                continue
            style = seg.style
            fg = _color_rgb(style.color if style else None, fg_default)
            bg = _color_rgb(style.bgcolor if style else None, bg_default)
            if style and style.bold and fg == fg_default:
                fg = (255, 255, 255)
            for ch in seg.text:
                if ch == "\n":
                    grid.append(current_line)
                    current_line = []
                else:
                    current_line.append((ch, fg, bg))
        if current_line:
            grid.append(current_line)

        # Strip trailing empty lines
        while grid and not grid[-1]:
            grid.pop()
        if not grid:
            grid = [[(" ", fg_default, bg_default)]]

        # Font setup
        font_size = 14
        font = _load_monospace_font(font_size)
        bbox = font.getbbox("M")
        char_w = bbox[2] - bbox[0]
        line_h = int(font_size * 1.5)

        max_cols = max(len(line) for line in grid)
        padding = 12
        img_w = max_cols * char_w + padding * 2
        img_h = len(grid) * line_h + padding * 2

        img = Image.new("RGB", (img_w, img_h), bg_default)
        draw = ImageDraw.Draw(img)

        for row_idx, line in enumerate(grid):
            y = padding + row_idx * line_h
            for col_idx, (ch, fg, bg) in enumerate(line):
                x = padding + col_idx * char_w
                if bg != bg_default:
                    draw.rectangle([x, y, x + char_w, y + line_h], fill=bg)
                draw.text((x, y), ch, fill=fg, font=font)

        buf = io.BytesIO()
        save_fmt = "JPEG" if fmt.lower() in ("jpg", "jpeg") else "PNG"
        img.save(buf, format=save_fmt)
        return buf.getvalue()


def _color_rgb(
    color: "rich.color.Color | None",  # noqa: F821
    default: tuple[int, int, int],
) -> tuple[int, int, int]:
    if color is None:
        return default
    try:
        from rich.color import ColorType
        from rich.terminal_theme import MONOKAI

        # DEFAULT color type returns (0,0,0) from get_truecolor() — use our default instead
        if color.type == ColorType.DEFAULT:
            return default
        # Remap standard ANSI colors (0-15) through MONOKAI theme palette.
        # Rich's default get_truecolor() uses classic values (e.g. blue=#000080)
        # that are unreadable on dark backgrounds.
        if color.type == ColorType.STANDARD and color.number is not None:
            palette = MONOKAI.ansi_colors._colors
            if color.number < len(palette):
                return palette[color.number]
        tc = color.get_truecolor()
        return (tc.red, tc.green, tc.blue)
    except Exception:
        return default


def _load_monospace_font(size: int) -> "ImageFont.FreeTypeFont":  # noqa: F821
    from PIL import ImageFont

    for path in [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()
