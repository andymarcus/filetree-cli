"""Side-effecting actions: opening files, revealing in Finder, copying paths.

Each returns a short human-readable status string suitable for a toast so the
app layer stays free of platform detail.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from textual.app import App

from filetree import styles


def _editor_command() -> list[str]:
    """Resolve the terminal editor to launch for text files."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        # $EDITOR may contain args, e.g. "code --wait".
        return editor.split()
    for candidate in ("nvim", "vim", "vi", "nano"):
        if shutil.which(candidate):
            return [candidate]
    return ["vi"]


def _system_open_command() -> list[str] | None:
    """The OS command that opens a path in its default app, or None."""
    if sys.platform == "darwin":
        return ["open"]
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        return ["xdg-open"]
    if os.name == "nt":
        return ["cmd", "/c", "start", ""]
    return None


def open_path(app: App, path: Path) -> str:
    """Open a file: text/code in the terminal editor, else the system default."""
    if path.is_dir():
        return ""  # directories are expanded by the tree, not "opened"

    if styles.is_text_file(path):
        command = [*_editor_command(), str(path)]
        # Suspend the TUI so the editor gets the real terminal, then restore.
        with app.suspend():
            try:
                subprocess.run(command, check=False)
            except OSError as error:
                return f"Could not launch editor: {error}"
        return f"Opened {path.name} in editor"

    open_command = _system_open_command()
    if open_command is None:
        return "No system open command available on this platform"
    try:
        subprocess.run([*open_command, str(path)], check=False)
    except OSError as error:
        return f"Could not open: {error}"
    return f"Opened {path.name}"


def reveal_in_finder(path: Path) -> str:
    """Reveal a path in the OS file manager (Finder on macOS)."""
    if sys.platform == "darwin":
        command = ["open", "-R", str(path)]
    elif sys.platform.startswith("linux") and shutil.which("xdg-open"):
        # No portable "reveal" on Linux; open the containing directory.
        target = path if path.is_dir() else path.parent
        command = ["xdg-open", str(target)]
    elif os.name == "nt":
        command = ["explorer", "/select,", str(path)]
    else:
        return "Reveal is not supported on this platform"
    try:
        subprocess.run(command, check=False)
    except OSError as error:
        return f"Could not reveal: {error}"
    return f"Revealed {path.name}"


def copy_path(app: App, path: Path) -> str:
    """Copy the absolute path to the clipboard."""
    text = str(path.resolve())
    # Prefer pbcopy on macOS (works over SSH-less local sessions reliably).
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return "Copied path to clipboard"
        except (OSError, subprocess.CalledProcessError):
            pass
    # Fall back to Textual's OSC 52 clipboard integration.
    try:
        app.copy_to_clipboard(text)
        return "Copied path to clipboard"
    except Exception:  # noqa: BLE001 - clipboard is best-effort
        return "Could not copy to clipboard"
