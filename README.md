# writing-lint

Two checkers over one rule file. `check-web-content` reads pages a browser
renders. `check-docs` reads comments, docstrings and markdown. Both report
the same way and both read `writing_lint/rules.toml`.

The checkers began as scripts bundled inside two editor skill archives.
A build pipeline cannot depend on an editor account, so they moved here.
Those archives now call the installed commands.

## Install

```sh
pipx install git+https://github.com/FoundingFuture/writing-lint@v1.0.0
```

A virtual environment works the same way.

```sh
uv venv .venv
uv pip install --python .venv/bin/python git+https://github.com/FoundingFuture/writing-lint@v1.0.0
```

Python 3.9 and later. Below 3.11 the package pulls in `tomli`, because
`tomllib` reached the standard library in 3.11.

## Commands

```sh
check-web-content content/                    every page under a directory
check-web-content --url https://example.org/  one published page
check-web-content --strict content/           warnings fail too
check-docs src/ docs/                         comments, docstrings, markdown
```

Both accept `--strict`, `--json` and `--quiet`. Both write one line per
finding:

```text
content/about.md:14: error: [word] banned word: robust
```

Exit code 0 means no errors. Exit code 1 means at least one error, or any
warning under `--strict`.

To skip one line, put `web-content:ignore` or `docs-style:ignore` on it. To
skip a whole file, put `web-content:ignore-file` in the first 30 lines, or
`docs-style:ignore-file` in the first 10.

## Rules

`writing_lint/rules.toml` holds every banned word, phrase, construct and
context term. `[shared]` is what both checkers agree on. `[web_content]`
and `[docs]` add to it. A term is banned, or it is a context term that
earns a warning where a technical reading is possible.

A rule change is an edit to that file plus a test. The tests assert exact
finding counts per fixture. An edit that widens a rule shows up as a number
that moved.

## Contract

A Hugo theme defines shortcodes and front matter keys that no other theme
has. `check-web-content --contract PATH` reads a `contract.toml` and treats
those names as known:

```toml
shortcodes = ["sources", "kind"]
front_matter = ["customField"]
```

Without the flag, the built-in Hugo list applies, and a theme name reads as
a warning. That is the right answer for a page meant to survive a change of
theme.

## Tests

```sh
uv pip install --python .venv/bin/python pytest
.venv/bin/python -m pytest
```
