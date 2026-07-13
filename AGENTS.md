# Project Instructions

This repository contains the reusable `x2telegram` package.

## Safety

- X reads must use bounded `bird` commands and JSON output.
- Never print or commit X or Telegram credentials.
- Telegram delivery is state-changing. Use `--dry-run` for development and tests.
- Save deduplication state only after every Telegram message chunk is accepted.

## Development

- Keep providers separated behind the source, summarizer, and sender interfaces.
- Keep the default package dependency-free on Python 3.11+.
- Run `python -m unittest discover -s tests -v` before committing.

