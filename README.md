# convdrift

`convdrift` detects stagnation and looping in human-LLM coding sessions by analyzing Claude Code transcript files.

The project reads JSONL transcripts, groups messages into **episodes** (one human prompt plus all resulting assistant/tool activity), and prepares the foundation for a future Drift Score that estimates when a session is becoming stuck.

## Status

The repository is currently in **Stage 0**:

- Python project initialized with `uv`
- `ruff` configured for code formatting
- JSONL transcript parsing
- Episode segmentation
- Sidechain separation
- Minimal CLI for episode summaries

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

Run the segmenter against the sample fixture:

```bash
uv run convdrift segment tests/fixtures/sample_transcript.jsonl
```

Example output:

```text
Transcript: tests/fixtures/sample_transcript.jsonl
Messages: 8
main: 2 episode(s)
  - episode 1: 4 message(s) [assistant=2, user=2]
  - episode 2: 2 message(s) [assistant=1, user=1]
sidechain:worker-1: 1 episode(s)
  - episode 1: 2 message(s) [assistant=1, user=1]
```

## Project Layout

```text
src/convdrift/        Core package
tests/                Pytest suite
tests/fixtures/       Sample transcript fixtures
DESIGN.md             Product and metric design
ROADMAP.md            Implementation stages
AGENTS.md             Contributor guide
```

## Notes

- Code formatting is standardized with `ruff`.
- Sidechains are analyzed independently from the mainline conversation.
