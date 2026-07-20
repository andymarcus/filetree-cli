"""The colour-coded file tree widget."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Iterable

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TreeNode

from filetree import styles

# Category -> colour. Chosen to read acceptably on both dark and light
# terminals. Colours live here (rather than the .tcss) because a tree label is
# a single Rich renderable that we style span-by-span in ``render_label``.
CATEGORY_COLORS: dict[str, str] = {
    "folder": "#5aa7ff",
    "code": "#63c98b",
    "docs": "#d9a35f",
    "image": "#c77dff",
    "config": "#e0c060",
    "archive": "#e06c75",
    "media": "#e084c4",
    "data": "#56b6c2",
    "shell": "#98c379",
    "binary": "#9aa0a6",
    "default": "#c9d1d9",
}
MUTED = "#7d8590"


class FileTree(DirectoryTree):
    """A ``DirectoryTree`` with icons, per-filetype colours, and metadata."""

    # Vim aliases and explicit left/right expand/collapse. Arrow up/down and
    # `enter` (open/toggle) come from the base Tree; we add the rest.
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("right,l", "expand_or_enter", "Expand", show=False),
        Binding("left,h", "collapse_or_leave", "Collapse", show=False),
    ]

    # When the terminal is narrow we drop the trailing size/metadata column.
    narrow: reactive[bool] = reactive(False)
    # Toggles whether dotfiles are shown. Reloading is driven by the app.
    show_hidden: reactive[bool] = reactive(True)

    def __init__(self, path: str | Path, **kwargs) -> None:
        super().__init__(str(path), **kwargs)
        # Cache of directory -> child count, keyed additionally by mtime so it
        # invalidates when the directory changes. Avoids re-listing on every
        # render of a visible folder row.
        self._child_count_cache: dict[Path, tuple[float, int]] = {}

    # -- Hidden-file filtering --------------------------------------------
    def filter_paths(self, paths: Iterable[Path]) -> list[Path]:
        if self.show_hidden:
            return list(paths)
        return [p for p in paths if not p.name.startswith(".")]

    # -- Reactions --------------------------------------------------------
    def watch_narrow(self, _old: bool, _new: bool) -> None:
        # Force every visible label to re-render with/without metadata.
        self.refresh()

    # -- Label rendering --------------------------------------------------
    def render_label(
        self, node: TreeNode[DirEntry], base_style: Style, style: Style
    ) -> Text:
        data = node.data
        if data is None:
            return Text("")

        path = data.path
        is_dir = path.is_dir()
        expanded = node.is_expanded and is_dir

        icon = styles.icon_for(path, is_dir, expanded)
        category = styles.category_for(path, is_dir)
        colour = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
        name = path.name or str(path)

        # `style` carries the cursor/highlight styling for this line (including
        # its background). Use it as the label's base so the highlighted row is
        # visible; our per-category spans set only a foreground colour, so that
        # background shows through.
        name_style = Style(color=colour, bold=is_dir)
        label = Text(style=style)
        label.append(f"{icon} ", name_style)
        label.append(name, name_style)

        if not self.narrow:
            meta = self._metadata(path, is_dir)
            if meta:
                label.append("  ")
                label.append(meta, Style(color=MUTED))

        return label

    # -- Metadata ---------------------------------------------------------
    def _metadata(self, path: Path, is_dir: bool) -> str:
        try:
            stat = path.stat()
        except OSError:
            return ""
        if is_dir:
            count = self._child_count(path, stat.st_mtime)
            if count is None:
                return ""
            return f"{count} item{'s' if count != 1 else ''}"
        return styles.human_size(stat.st_size)

    def _child_count(self, path: Path, mtime: float) -> int | None:
        cached = self._child_count_cache.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        try:
            with os.scandir(path) as entries:
                count = sum(
                    1
                    for entry in entries
                    if self.show_hidden or not entry.name.startswith(".")
                )
        except OSError:
            return None
        self._child_count_cache[path] = (mtime, count)
        return count

    # -- Navigation actions ----------------------------------------------
    def action_expand_or_enter(self) -> None:
        """Right/l: expand a collapsed folder, or step into an open one."""
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand:
            if node.is_expanded:
                self.action_cursor_down()
            else:
                node.expand()

    def action_collapse_or_leave(self) -> None:
        """Left/h: collapse an open folder, else move up to the parent."""
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None:
            self.move_cursor(node.parent)

    # -- Reveal a path (used by search) -----------------------------------
    async def reveal_path(self, target: Path) -> None:
        """Expand ancestors of ``target`` and move the cursor onto it.

        Children load asynchronously, so we poll briefly for each level to
        appear before descending.
        """
        try:
            parts = target.relative_to(self.path).parts
        except ValueError:
            return

        node = self.root
        if not node.is_expanded:
            node.expand()
        await self._await_children(node)

        for index, part in enumerate(parts):
            match = next(
                (
                    child
                    for child in node.children
                    if child.data is not None and child.data.path.name == part
                ),
                None,
            )
            if match is None:
                break
            node = match
            is_last = index == len(parts) - 1
            if node.allow_expand and (not is_last or target.is_dir()):
                if not node.is_expanded:
                    node.expand()
                await self._await_children(node)

        self.move_cursor(node, animate=True)

    async def _await_children(self, node: TreeNode[DirEntry], timeout: float = 0.75) -> None:
        """Wait until a just-expanded node has loaded its children (or times out)."""
        if node.data is None or not node.allow_expand:
            return
        elapsed = 0.0
        step = 0.02
        while not node.children and elapsed < timeout:
            await asyncio.sleep(step)
            elapsed += step
