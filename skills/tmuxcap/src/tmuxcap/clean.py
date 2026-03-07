"""Strip TUI decoration characters from captured terminal text."""

# Box-drawing and decorative characters (visual noise, no semantic value)
_TUI_CHARS = set("─━│┃┌┐└┘├┤┬┴┼╭╮╯╰═║╔╗╚╝╠╣╦╩╬░▒▓█⎽⎼⎻⎺")


def clean_lines(text: str) -> str:
    """Strip TUI decoration characters from each line, dropping empty results."""
    result = []
    for line in text.split("\n"):
        cleaned = "".join(ch for ch in line if ch not in _TUI_CHARS)
        if cleaned.strip():
            result.append(cleaned)
    return "\n".join(result)
