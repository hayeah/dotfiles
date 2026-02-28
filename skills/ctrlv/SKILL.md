---
name: ctrlv
description: Saves macOS clipboard contents to files in a .ctrlv/ subdirectory. Use when the user wants to paste clipboard items (text, images, or files) to disk.
---

# ctrlv

Saves the macOS clipboard to files in a `.ctrlv/` subdirectory.

## Install

```bash
uv tool install -e .
```

## Usage

```
ctrlv [OUTPUT_PATH]
```

`OUTPUT_PATH` defaults to `~` (home directory). Files are always written to `OUTPUT_PATH/.ctrlv/`, named `1.ext`, `2.ext`, etc. The directory is wiped on every run.

## Options

| Flag | Description |
|------|-------------|
| `-l`, `--list` | Preview clipboard contents without writing |
| `-a`, `--add` | Append to `.ctrlv/` instead of wiping it first |
| `--ssh <host>` | Rsync `.ctrlv/` to the same path on a remote SSH host |

## Output format

Each item is printed as one line:

```
 1  file: /Users/me/Downloads/photo.jpg
 2  text: 'hello world'
 3  image (png, 204,800 bytes)
```

## File naming

Files use their original name. Unnamed content (text, images) gets the item's index number. File name collisions get a `_{i}` suffix before the extension:

| Clipboard content | Written as |
|-------------------|------------|
| Text | `1.txt`, `2.txt`, ... |
| Image (PNG) | `1.png`, `2.png`, ... |
| Image (JPEG) | `1.jpg`, `2.jpg`, ... |
| Image (TIFF) | `1.tiff`, `2.tiff`, ... |
| File | `original.pdf`, `original_2.pdf`, ... |
| File (no extension) | `Makefile`, `Makefile_2`, ... |

When multiple files are copied (e.g. from Finder), each becomes a separate item.

## Examples

```bash
# Paste to ~/.ctrlv/
ctrlv

# Paste to ~/Desktop/.ctrlv/
ctrlv ~/Desktop

# Preview without writing
ctrlv --list
ctrlv -l

# Append clipboard to existing .ctrlv/ (paste multiple times)
ctrlv --add
ctrlv -a

# Paste locally and rsync to remote host
ctrlv --ssh m4mini

# Paste to custom dir and rsync to remote
ctrlv ~/projects --ssh m4mini
```

## Notes

- Reads the system pasteboard via `NSPasteboard`, which includes iCloud Universal Clipboard automatically when the Mac is signed into iCloud.
- Item priority per clipboard slot: file URL > image > text.
- If the same copy action produces both a file URL and a text representation (e.g. Finder copies), only the file is captured.
- With `--ssh`, the remote `.ctrlv/` directory is synced with `rsync --delete`, so only the current paste contents remain on the remote.
