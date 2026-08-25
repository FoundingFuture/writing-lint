# Changelog

## v1.0.1, 2026-08-26

- A GitHub alert opened a blockquote with a bracketed keyword, and the
  keyword was read as an exclamation mark in prose. It is markup, so it
  is stripped before the character rules run.

## v1.0.0, 2026-08-26

First release. The checkers moved out of two editor skill archives into
a package the build pipeline installs by tag.

- `check-web-content` and `check-docs` are entry points of one package.
- Every banned word, phrase, construct and context term moved into
  `writing_lint/rules.toml`, under `[shared]`, `[web_content]` and `[docs]`.
- `check-web-content --contract PATH` reads a theme contract and treats its
  shortcodes and front matter keys as known.
- `check-web-content` warns on a front matter key that is not a Hugo key and
  is not named in a contract. A custom key belongs under `params`.
- The docs checker matched a straight apostrophe only. It now matches the
  curly form too, which is what the web checker already did.
- The docs word list held `plethora` twice, so one line reported it twice.
- Four banned character messages now read the same in both checkers.
