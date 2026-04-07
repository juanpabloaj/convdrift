# convdrift

`convdrift` detects stagnation and looping in human-LLM coding sessions by analyzing Claude Code transcript files.

The tool reads JSONL transcripts, groups messages into **episodes** (one human prompt plus all resulting assistant/tool activity), and produces a Drift Score (0–100) that estimates when a session is becoming stuck.

## Status

The repository is currently in **Stage 3** (output layer complete):

- JSONL transcript parsing and episode segmentation
- Tier 1 metrics: tool error rate, action mix, user message length trend
- Tier 2 metrics: lexical stagnation index, correction density
- Composite Drift Score with configurable weights and thresholds
- Claude Code statusline integration via `statusline-run`
- Per-session drift timeline log

See `DESIGN.md` for the full product rationale and `ROADMAP.md` for staged implementation details.

## Requirements

- Python 3.12+
- `uv`

## Quick Start

Install dependencies and lock the environment:

```bash
uv lock
```

Format the codebase:

```bash
uv run ruff format .
```

Run the test suite:

```bash
uv run pytest
```

Compute the drift score for a transcript:

```bash
uv run convdrift run /path/to/transcript.jsonl
```

List recorded sessions:

```bash
uv run convdrift sessions
```

Print the drift timeline for a past session:

```bash
uv run convdrift log <session_id>
```

Generate a default config file:

```bash
uv run convdrift config init
```

## Project Layout

```text
src/convdrift/        Core package
scripts/              Shell scripts (statusline integration)
tests/                Pytest suite
tests/fixtures/       Sample transcript fixtures
DESIGN.md             Product and metric design
ROADMAP.md            Implementation stages
AGENTS.md             Contributor guide
```

## Claude Statusline Integration

`scripts/statusline.sh` is designed for Claude Code's statusline. Claude Code pipes a JSON object to stdin with session metadata; the script forwards that payload to `convdrift statusline-run`, which performs a one-shot analysis, updates the centralized score store, and prints a compact drift indicator.

**Requirements**: `uv` must be in the `PATH` of the shell that Claude Code uses (typically your login shell). Verify with `which uv`.

Add to `~/.claude/settings.json`:

```json
{
  "statusCommand": "/path/to/convdrift/scripts/statusline.sh"
}
```

The default output format is `score-only` (`D:42`). Override via environment variable:

```json
{
  "statusCommand": "CONVDRIFT_OUTPUT_FORMAT=with-metrics /path/to/convdrift/scripts/statusline.sh"
}
```

Available formats: `score-only` · `with-metrics` · `by-tier` · `full`

By default, convdrift stores scores in `~/.convdrift/store.sqlite3` and session timelines in `~/.convdrift/sessions/<session_id>.jsonl`. Override the store location with `CONVDRIFT_STORE_PATH` only if you have a specific reason to do so.

Each invocation of the statusline script runs a full one-shot analysis and updates the store — no separate process required.

## Notes

- Code formatting is standardized with `ruff`.
- Sidechains are analyzed independently from the mainline conversation.

## References

- https://code.claude.com/docs/en/statusline
