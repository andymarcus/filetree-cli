"""The filetree Textual application and CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from filetree import __version__, actions
from filetree.search import SearchScreen
from filetree.tree import FileTree

# Below this terminal width we drop the size/metadata column to keep names readable.
NARROW_WIDTH = 60


def _display_path(path: Path) -> str:
    """Collapse the home directory to ``~`` for a tidy header."""
    home = Path.home()
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


class FileTreeApp(App[None]):
    """Interactive, colour-coded file-tree browser."""

    CSS_PATH = "filetree.tcss"

    BINDINGS = [
        Binding("slash", "search", "Search"),
        Binding("c", "copy", "Copy path"),
        Binding("r", "reveal", "Reveal"),
        Binding("full_stop", "toggle_hidden", "Hidden"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def __init__(self, root: Path, watch: bool = True, refresh_interval: float = 1.0) -> None:
        super().__init__()
        self._root = root
        self._watch = watch
        self._refresh_interval = refresh_interval

    def compose(self) -> ComposeResult:
        yield Header()
        yield FileTree(self._root, id="tree")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "filetree"
        self.sub_title = _display_path(self._root)
        tree = self.query_one(FileTree)
        tree.show_root = True
        tree.guide_depth = 3
        tree.root.expand()
        tree.focus()
        self._apply_narrow(self.size.width)
        if self._watch:
            # Auto-reload directories when they change on disk.
            tree.start_watching(self._refresh_interval)

    # -- Responsiveness ---------------------------------------------------
    def on_resize(self, event) -> None:  # noqa: ANN001 - Textual Resize event
        self._apply_narrow(event.size.width)

    def _apply_narrow(self, width: int) -> None:
        self.query_one(FileTree).narrow = width < NARROW_WIDTH

    # -- Opening ----------------------------------------------------------
    @on(FileTree.FileSelected)
    def _on_file_selected(self, event: FileTree.FileSelected) -> None:
        self._open(event.path)

    def _open(self, path: Path) -> None:
        status = actions.open_path(self, path)
        if status:
            self.notify(status)

    # -- Keyboard actions -------------------------------------------------
    def _cursor_path(self) -> Path | None:
        node = self.query_one(FileTree).cursor_node
        if node is not None and node.data is not None:
            return node.data.path
        return None

    def action_copy(self) -> None:
        path = self._cursor_path()
        if path is not None:
            self.notify(actions.copy_path(self, path))

    def action_reveal(self) -> None:
        path = self._cursor_path()
        if path is not None:
            self.notify(actions.reveal_in_finder(path))

    def action_toggle_hidden(self) -> None:
        tree = self.query_one(FileTree)
        tree.show_hidden = not tree.show_hidden
        tree.reload()
        self.notify(
            "Showing hidden files" if tree.show_hidden else "Hiding hidden files"
        )

    def action_search(self) -> None:
        tree = self.query_one(FileTree)

        def _on_dismiss(result: Path | None) -> None:
            if result is not None:
                self._handle_search_result(result)

        self.push_screen(SearchScreen(self._root, tree.show_hidden), _on_dismiss)

    def _handle_search_result(self, path: Path) -> None:
        tree = self.query_one(FileTree)
        tree.focus()
        if path.is_dir():
            self.run_worker(tree.reveal_path(path), exclusive=True)
        else:
            self.run_worker(self._reveal_then_open(path), exclusive=True)

    async def _reveal_then_open(self, path: Path) -> None:
        # Move the cursor onto the file in the tree, then open it.
        await self.query_one(FileTree).reveal_path(path)
        self._open(path)

    def action_help(self) -> None:
        self.notify(
            "↑/↓ or j/k move   ←/→ or h/l fold   ⏎ open   c copy path   "
            "r reveal in Finder   / search   . toggle hidden   q quit",
            title="filetree keys",
            timeout=8,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="filetree",
        description="An interactive, colour-coded file-tree browser for your terminal.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to browse (defaults to the current directory).",
    )
    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Disable auto-refresh when files change on disk.",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="How often to poll for on-disk changes (default: 1.0).",
    )
    parser.add_argument("-V", "--version", action="version", version=f"filetree {__version__}")
    args = parser.parse_args()

    root = Path(args.path).expanduser()
    try:
        root = root.resolve()
    except OSError:
        pass
    if not root.exists():
        print(f"filetree: {args.path}: no such file or directory", file=sys.stderr)
        raise SystemExit(1)
    if not root.is_dir():
        root = root.parent

    FileTreeApp(
        root,
        watch=not args.no_watch,
        refresh_interval=max(0.1, args.refresh),
    ).run()


if __name__ == "__main__":
    main()
