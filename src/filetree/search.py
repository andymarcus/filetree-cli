"""Fuzzy search overlay (opened with `/`).

Walks the tree once (from the invocation root downward), then fuzzy-matches
against the relative path of every entry as the user types. Returns the chosen
``Path`` to the app, which opens files and jumps to directories.
"""

from __future__ import annotations

import os
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

# Hard ceiling so an accidental run at `/` doesn't walk the whole disk. If we
# hit it we tell the user rather than silently searching a partial tree.
MAX_ENTRIES = 20_000
# How many matches to render at once.
MAX_RESULTS = 200


class SearchScreen(ModalScreen[Path | None]):
    """A modal fuzzy finder over everything beneath the root directory."""

    BINDINGS = [
        Binding("escape", "dismiss_search", "Close", show=False),
        Binding("down", "cursor_down", "Next", show=False),
        Binding("up", "cursor_up", "Previous", show=False),
        Binding("enter", "choose", "Open", show=False),
    ]

    def __init__(self, root: Path, show_hidden: bool) -> None:
        super().__init__()
        self._root = root
        self._show_hidden = show_hidden
        self._entries: list[tuple[str, Path]] = []  # (relative-path, absolute)
        self._matches: list[Path] = []
        self._truncated = False

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Input(placeholder="Fuzzy search files and folders…", id="search-input")
            yield Label("", id="search-note")
            yield OptionList(id="search-results")

    def on_mount(self) -> None:
        self._build_index()
        note = self.query_one("#search-note", Label)
        if self._truncated:
            note.update(
                f"Showing first {MAX_ENTRIES:,} entries — refine near the root for the rest."
            )
        else:
            note.display = False
        self._update_results("")
        self.query_one("#search-input", Input).focus()

    # -- Index ------------------------------------------------------------
    def _build_index(self) -> None:
        count = 0
        for dirpath, dirnames, filenames in os.walk(self._root):
            if not self._show_hidden:
                # Prune hidden directories in place so os.walk doesn't descend.
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                filenames = [f for f in filenames if not f.startswith(".")]
            base = Path(dirpath)
            for name in sorted(dirnames) + sorted(filenames):
                absolute = base / name
                try:
                    relative = absolute.relative_to(self._root)
                except ValueError:
                    relative = absolute
                self._entries.append((str(relative), absolute))
                count += 1
                if count >= MAX_ENTRIES:
                    self._truncated = True
                    return

    # -- Matching ---------------------------------------------------------
    @on(Input.Changed, "#search-input")
    def _on_query_changed(self, event: Input.Changed) -> None:
        self._update_results(event.value)

    def _update_results(self, query: str) -> None:
        results = self.query_one("#search-results", OptionList)
        results.clear_options()
        self._matches = []

        if not query.strip():
            # Show a first slice so the list isn't empty on open.
            for relative, absolute in self._entries[:MAX_RESULTS]:
                self._matches.append(absolute)
                results.add_option(Option(relative))
            return

        matcher = Matcher(query)
        scored: list[tuple[float, str, Path]] = []
        for relative, absolute in self._entries:
            score = matcher.match(relative)
            if score > 0:
                scored.append((score, relative, absolute))
        scored.sort(key=lambda item: item[0], reverse=True)

        for _score, relative, absolute in scored[:MAX_RESULTS]:
            self._matches.append(absolute)
            results.add_option(Option(matcher.highlight(relative)))

    # -- Actions ----------------------------------------------------------
    def action_dismiss_search(self) -> None:
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        self.query_one("#search-results", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#search-results", OptionList).action_cursor_up()

    def action_choose(self) -> None:
        results = self.query_one("#search-results", OptionList)
        index = results.highlighted
        if index is not None and 0 <= index < len(self._matches):
            self.dismiss(self._matches[index])

    @on(OptionList.OptionSelected, "#search-results")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if 0 <= index < len(self._matches):
            self.dismiss(self._matches[index])
