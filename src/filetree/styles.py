"""Filetype styling: colour categories, icons, and file-nature detection.

A file's *category* drives both its colour (via a CSS class in ``filetree.tcss``)
and its icon. We map by extension, with a handful of well-known filenames handled
specially (e.g. ``Dockerfile``, ``Makefile``).
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Categories -----------------------------------------------------------
# Each category has a colour (defined in filetree.tcss as `.cat-<name>`) and a
# pair of icons: a Nerd Font glyph and an ASCII fallback.

# Nerd Font glyphs (require a patched font). Fallbacks are plain ASCII.
_NERD_ICONS = {
    "folder": "",       #
    "folder_open": "",  #
    "code": "",         #
    "docs": "",         #
    "image": "",        #
    "config": "",       #
    "archive": "",      #
    "media": "",        #
    "data": "",         #
    "shell": "",        #
    "binary": "",       #
    "default": "",      #
}

_ASCII_ICONS = {
    "folder": "▸",       # ▸
    "folder_open": "▾",  # ▾
    "code": "<>",
    "docs": "¶",         # ¶
    "image": "▣",        # ▣
    "config": "⚙",       # ⚙
    "archive": "≣",      # ≣
    "media": "♪",        # ♪
    "data": "☷",         # ☷
    "shell": "$_",
    "binary": "▪",       # ▪
    "default": "·",      # ·
}

# Extension -> category.
_EXT_CATEGORY: dict[str, str] = {}


def _register(category: str, *extensions: str) -> None:
    for ext in extensions:
        _EXT_CATEGORY[ext] = category


_register(
    "code",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb", ".java", ".c",
    ".h", ".cpp", ".hpp", ".cc", ".cs", ".php", ".swift", ".kt", ".scala",
    ".lua", ".pl", ".r", ".dart", ".ex", ".exs", ".clj", ".hs", ".ml",
    ".vue", ".svelte", ".sql",
)
_register(
    "docs",
    ".md", ".markdown", ".rst", ".txt", ".text", ".adoc", ".org", ".tex",
    ".pdf", ".doc", ".docx", ".rtf", ".epub",
)
_register(
    "image",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico",
    ".tiff", ".tif", ".heic", ".avif",
)
_register(
    "config",
    ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".env",
    ".properties", ".lock", ".editorconfig", ".gitignore", ".gitattributes",
    ".dockerignore",
)
_register(
    "archive",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".zst",
    ".jar", ".war", ".dmg", ".iso",
)
_register(
    "media",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac",
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv",
)
_register(
    "data",
    ".csv", ".tsv", ".parquet", ".xls", ".xlsx", ".db", ".sqlite", ".sqlite3",
    ".xml", ".ndjson",
)
_register(
    "shell",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
)
_register(
    "binary",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".bin", ".class", ".pyc",
    ".wasm",
)

# Special-cased exact filenames (no useful extension).
_FILENAME_CATEGORY: dict[str, str] = {
    "dockerfile": "config",
    "makefile": "code",
    "cmakelists.txt": "code",
    "license": "docs",
    "readme": "docs",
    ".gitignore": "config",
    ".env": "config",
}

# Extensions that we treat as text for the purposes of "smart open".
_TEXT_EXTENSIONS = (
    set(_EXT_CATEGORY)
    - {ext for ext, cat in _EXT_CATEGORY.items()
       if cat in ("image", "archive", "media", "binary")}
    - {".pdf", ".doc", ".docx", ".rtf", ".epub", ".xls", ".xlsx",
       ".db", ".sqlite", ".sqlite3", ".parquet"}
)


def _use_nerd_font() -> bool:
    """Whether to use Nerd Font glyphs (on) or plain ASCII icons (off).

    There is no reliable programmatic detection, so this is controlled by the
    ``FILETREE_NERD_FONT`` environment variable. It defaults to OFF (ASCII icons,
    which render in any terminal); set it to ``1``/``true`` to enable Nerd Font
    glyphs if your terminal font supports them.
    """
    value = os.environ.get("FILETREE_NERD_FONT", "").strip().lower()
    return value in ("1", "true", "yes", "on")


USE_NERD_FONT = _use_nerd_font()
_ICONS = _NERD_ICONS if USE_NERD_FONT else _ASCII_ICONS


def category_for(path: Path, is_dir: bool) -> str:
    """Return the style category for a path."""
    if is_dir:
        return "folder"
    name = path.name.lower()
    if name in _FILENAME_CATEGORY:
        return _FILENAME_CATEGORY[name]
    # Compound extensions like .tar.gz -> use the last suffix.
    suffix = path.suffix.lower()
    return _EXT_CATEGORY.get(suffix, "default")


def icon_for(path: Path, is_dir: bool, expanded: bool = False) -> str:
    """Return the icon glyph for a path."""
    if is_dir:
        return _ICONS["folder_open"] if expanded else _ICONS["folder"]
    category = category_for(path, is_dir=False)
    return _ICONS.get(category, _ICONS["default"])


def is_text_file(path: Path) -> bool:
    """Heuristically decide whether a file is text (open in editor) vs binary.

    First trust the extension allow-list; otherwise sniff the first chunk for
    NUL bytes, which reliably indicate binary content.
    """
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return True
    if suffix in _EXT_CATEGORY:  # known, but not a text category
        return False
    if path.name.lower() in _FILENAME_CATEGORY:
        return _FILENAME_CATEGORY[path.name.lower()] != "binary"
    try:
        with path.open("rb") as handle:
            chunk = handle.read(2048)
    except OSError:
        return False
    if not chunk:
        return True  # empty file — treat as text
    if b"\x00" in chunk:
        return False
    # If it decodes as UTF-8, call it text.
    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def human_size(num_bytes: int) -> str:
    """Format a byte count like ``1.2 KB``."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
