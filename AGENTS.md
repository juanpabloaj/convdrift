# Repository Guidelines

## Project Structure & Module Organization

Core code lives in `src/convdrift/`. Keep parsing and transcript ingestion in `parser.py`, data models in `models.py`, episode grouping in `segmenter.py`, and CLI entrypoints in `cli.py`. Tests live in `tests/`, with reusable transcript samples under `tests/fixtures/`. High-level product intent and implementation phases are documented in `DESIGN.md`, `ROADMAP.md`, and `CLAUDE.md`.

## Build, Test, and Development Commands

- `uv lock`: resolve and refresh dependency locking in `uv.lock`.
- `uv run ruff format .`: format the repository with the canonical formatter.
- `uv run pytest`: run the full test suite.
- `uv run convdrift segment tests/fixtures/sample_transcript.jsonl`: exercise the Stage 0 CLI against a known fixture.
- `uv run python -m convdrift segment <path-to-transcript>`: run the CLI module directly during development.

Use Python 3.12 as defined in `.python-version` and `pyproject.toml`.

## Coding Style & Naming Conventions

Write all code, comments, and documentation in English. Use 4-space indentation, type hints, and small focused modules. Prefer `snake_case` for functions, variables, and module names; use `PascalCase` for dataclasses and other types. Keep parsing logic tolerant to transcript schema variations and avoid embedding Claude-Code-specific assumptions unless they are documented in `DESIGN.md`.

Use `ruff format` before submitting code changes. Keep imports, names, and docstrings consistent with the standard library-first approach already in the repository.

## Testing Guidelines

Tests use `pytest`. Name files `test_*.py` and keep fixtures small, readable, and representative of real transcript shapes. Add or update tests whenever parser behavior, segmentation rules, or CLI output changes. Prefer assertions on observable behavior, such as episode counts, role distribution, and sidechain handling.

## Commit & Pull Request Guidelines

Git history is currently minimal (`added DESIGN.md`), so follow a simple convention: short imperative commit subjects describing the change, for example `add episode segmentation tests` or `fix CLI subcommand registration`.

Pull requests should include:

- a brief summary of the change,
- links to any relevant roadmap stage or issue,
- confirmation that `uv run ruff format .` was run when code changed,
- test evidence (`uv run pytest` output or equivalent),
- sample CLI output when changing user-facing commands.

## Architecture Notes

The unit of analysis is the episode, not an individual message. Preserve the separation between mainline and sidechains unless a later roadmap stage explicitly changes that behavior.
