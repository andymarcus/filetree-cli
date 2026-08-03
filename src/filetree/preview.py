"""Rendered Markdown preview, shown instead of the editor for ``.md`` files.

Opening a Markdown file renders it in-app — headings, lists, tables, code
blocks, a table of contents, and relative links to other Markdown documents.
``e`` hands the file to the editor when the raw source is what you wanted.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, MarkdownViewer

from filetree import styles

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdwn"}

# The renderer builds a widget per block, so very large documents are slow
# enough that the editor is the kinder answer.
MAX_PREVIEW_BYTES = 2 * 1024 * 1024

# What the screen dismisses with when the user asks for the raw source.
OPEN_IN_EDITOR = "editor"

# Link schemes we hand to the browser rather than the filesystem.
_WEB_SCHEMES = {"http", "https", "mailto"}


def is_markdown(path: Path) -> bool:
    """Whether a path looks like a Markdown document."""
    return path.suffix.lower() in MARKDOWN_EXTENSIONS


def within_size_limit(path: Path) -> bool:
    """Whether the file is small enough to render comfortably."""
    try:
        return path.stat().st_size <= MAX_PREVIEW_BYTES
    except OSError:
        return False


def read_document(path: Path) -> str | None:
    """Read a Markdown file, or None if it can't be read.

    Undecodable bytes are replaced rather than fatal — a mostly-text document
    should still render.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


class _Viewer(MarkdownViewer):
    """A ``MarkdownViewer`` that screens link targets before following them.

    The stock viewer routes every clicked href through ``go()``, which reads it
    as a file — so an ``https://`` link raises. Filtering inside ``go()`` (rather
    than in a link-clicked handler) keeps one code path: Textual also dispatches
    the base class's own handler, so an override there would fire twice.
    """

    async def go(self, location: str | PurePath) -> None:
        href = str(location)
        scheme = urlparse(href).scheme.lower()
        if scheme in _WEB_SCHEMES:
            self.app.open_url(href)
            return
        if scheme:  # some other protocol — not ours to resolve
            self.notify(f"Can't open {href}", severity="warning")
            return

        target, _, _anchor = href.partition("#")
        if target:
            if not is_markdown(Path(target)):
                self.notify(f"Not a Markdown file: {target}", severity="warning")
                return
            # Resolve like the navigator does, so a broken link is reported
            # rather than leaving the history pointing at a missing file.
            resolved = self.navigator.location.parent / Path(target)
            if not resolved.is_file():
                self.notify(f"No such file: {target}", severity="warning")
                return
            if not within_size_limit(resolved):
                self.notify(f"Too large to render: {target}", severity="warning")
                return
        try:
            await super().go(location)
        except OSError as error:
            self.notify(f"Could not open {target or href}: {error}", severity="warning")


class MarkdownScreen(ModalScreen[str | None]):
    """Modal that renders a Markdown document."""

    BINDINGS = [
        Binding("escape,q", "close", "Close", show=False),
        Binding("e", "open_raw", "Open raw", show=False),
        Binding("t", "toggle_contents", "Contents", show=False),
        Binding("b", "back", "Back", show=False),
        # The tree takes vim keys, so the viewer does too (arrows, page keys and
        # home/end come from MarkdownViewer itself).
        Binding("j", "scroll_doc(1)", "Scroll down", show=False),
        Binding("k", "scroll_doc(-1)", "Scroll up", show=False),
    ]

    def __init__(self, path: Path, text: str) -> None:
        super().__init__()
        self._path = path
        self._text = text

    def compose(self) -> ComposeResult:
        with Vertical(id="md-box"):
            yield Label(styles.display_path(self._path), id="md-title")
            # The text is passed up front so the viewer renders it as it mounts
            # (the navigator is primed in on_mount so relative links resolve
            # against this file rather than the working directory).
            # open_links=False leaves link handling to `_Viewer.go` — otherwise
            # the document also fires every href straight at the browser.
            yield _Viewer(
                self._text,
                show_table_of_contents=False,
                open_links=False,
                id="md-viewer",
            )
            yield Label(
                "↑/↓ or j/k scroll   t contents   b back   e open raw   esc close",
                id="md-hint",
            )

    def on_mount(self) -> None:
        viewer = self.query_one("#md-viewer", _Viewer)
        viewer.navigator.go(self._path)
        viewer.document.focus()

    def on_markdown_viewer_navigator_updated(self) -> None:
        # Following a link (or going back) changes which document we're showing.
        viewer = self.query_one("#md-viewer", _Viewer)
        self.query_one("#md-title", Label).update(
            styles.display_path(viewer.navigator.location)
        )

    # -- Actions ----------------------------------------------------------
    def action_close(self) -> None:
        self.dismiss(None)

    def action_open_raw(self) -> None:
        self.dismiss(OPEN_IN_EDITOR)

    def action_toggle_contents(self) -> None:
        viewer = self.query_one("#md-viewer", _Viewer)
        viewer.show_table_of_contents = not viewer.show_table_of_contents

    async def action_back(self) -> None:
        await self.query_one("#md-viewer", _Viewer).back()

    def action_scroll_doc(self, lines: int) -> None:
        self.query_one("#md-viewer", _Viewer).scroll_relative(y=lines, animate=False)
