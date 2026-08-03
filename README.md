# filetree

An interactive, colour-coded file-tree browser for your terminal. Run it in any
directory to navigate the tree with the keyboard, open files, copy paths, reveal
in Finder, and fuzzy-search — all without leaving the terminal.

## Install

Requires **Python 3.10+**. [`pipx`](https://pipx.pypa.io/) is recommended — it
installs the tool in its own isolated environment and puts `filetree` on your
PATH.

```bash
# Install straight from GitHub (recommended)
pipx install git+https://github.com/andymarcus/filetree-cli.git
```

No `pipx`? Either `python3 -m pip install --user pipx && pipx ensurepath`, or
install with pip directly:

```bash
pip install --user git+https://github.com/andymarcus/filetree-cli.git
```

To update to the latest version later:

```bash
pipx upgrade filetree      # or: pipx reinstall filetree
```

Then run it:

```bash
filetree            # browse the current directory
filetree ~/code     # browse a specific directory
```

### Development install

```bash
git clone https://github.com/andymarcus/filetree-cli.git
cd filetree-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

You can also run it without installing, from the project root:

```bash
python -m filetree
```

## Keys

| Key | Action |
| --- | --- |
| `↑` / `↓` or `j` / `k` | Move up / down |
| `→` / `l` | Expand folder (or step into an open one) |
| `←` / `h` | Collapse folder (or move to parent) |
| `Enter` | Open file (Markdown renders in-app, editor for other text, system app otherwise); toggle folders |
| `e` | Open the highlighted file raw — skips the Markdown preview |
| `c` | Copy the highlighted item's full path to the clipboard |
| `r` | Reveal the highlighted item in Finder |
| `/` | Fuzzy-search files and folders beneath the start directory |
| `.` | Toggle hidden (dot) files (shown by default) |
| `?` | Show the key reference |
| `q` / `Esc` | Quit |

## Notes

- **Auto-refresh**: the tree watches the directories you have open and reloads
  them automatically when files are added, removed, or renamed on disk — your
  expanded folders and cursor position are preserved. It polls once a second by
  default; tune it with `--refresh SECONDS`, or turn it off with `--no-watch`
  (handy for very large trees or network filesystems).
- **Opening files** is *smart*: Markdown renders in-app, other text and code
  files open in your `$EDITOR` (falling back to `nvim`/`vim`/`nano`), and
  everything else opens in the system default app (macOS `open`, Linux
  `xdg-open`).
- **Markdown preview**: `.md` files (and `.markdown`, `.mkd`, `.mdown`) open in
  a rendered view — headings, lists, tables, and code blocks — rather than as
  raw source. Inside it: `↑`/`↓` or `j`/`k` scroll, `t` toggles a table of
  contents, `Esc`/`q` closes, and `e` reopens the file in your editor. Links to
  other Markdown files are followed in place, with `b` to go back; web links
  open in your browser. Documents over 2 MB go straight to the editor.
- **Icons**: plain ASCII icons are used by default so the tree renders in any
  terminal. If your terminal font is a [Nerd Font](https://www.nerdfonts.com/),
  set `FILETREE_NERD_FONT=1` for richer filetype glyphs.
- **Search** only looks at files and folders from the start directory downward,
  and is capped at 20,000 entries (it tells you if it hit the cap).
- The layout is responsive: the size/metadata column and footer hints adapt to
  the terminal width.
