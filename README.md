# convdrift

`convdrift` detects stagnation and looping in human-LLM coding sessions by analyzing Claude Code transcript files.

The tool reads JSONL transcripts, groups messages into **episodes** (one human prompt plus all resulting assistant/tool activity), and produces a Drift Score (0–100) that estimates when a session is becoming stuck.

## Output

### Statusline indicator (`statusline-run`)

Compact single-line output shown in the Claude Code statusline:

```
Healthy 19 | corrections 60%
```

The label describes the current band; the number is the Drift Score (0–100); signals above the 20% threshold appear after the pipe, ranked by strength.

### Analysis report (`run`)

Verbose output for manual inspection:

```
Drift score: 26 (mild drift)
Window: last 5 episodes (93 total)
Diagnosis: Strongest signal in this window: user corrections (40%).
Signals:
- Tool errors: 5%
- Repetition: 3%
- User corrections: 40%
- User re-explaining: 0%
Assistant activity:
- Productive: 33%
- Exploratory: 62%
- Recursive: 0%
- Neutral: 5%
Technical detail:
- Raw score: 21.59
- Structural: 23.81
- Lexical: 17.90
```

### Score interpretation

| Score | Band | Meaning |
|-------|------|---------|
| 0–25 | **Healthy** | Forward progress, low error rate |
| 25–50 | **Mild drift** | Some repetition or unproductive exploration |
| 50–75 | **Significant drift** | Multiple degradation signals active |
| 75–100 | **Stuck** | Session is looping; consider starting a new session |

### Signals

| Signal | What it measures |
|--------|-----------------|
| `errors` | Proportion of tool calls that returned errors |
| `repetition` | N-gram overlap across recent assistant responses |
| `corrections` | User messages containing correction markers ("no", "that's wrong", "again", etc.) |
| `re-explaining` | User messages growing longer over time (escalating re-explanation) |

---

## Status

The repository is currently in **Stage 3.5** (pre-Stage 4 hardening complete):

- JSONL transcript parsing and episode segmentation
- Structural metrics (T1): tool error rate, action mix, user message length trend
- Lexical metrics (T2): lexical stagnation index, correction marker rate
- Composite Drift Score with configurable weights and thresholds
- Claude Code statusline integration via `statusline-run`
- Per-session drift timeline log (immutable event log)

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

The default output format is `with-metrics` (`Healthy 19 | corrections 60%`). Override via `--output-format`:

```json
{
  "statusCommand": "CONVDRIFT_OUTPUT_FORMAT=score-only /path/to/convdrift/scripts/statusline.sh"
}
```

Supported formats for `statusline-run`: `with-metrics` (default) · `score-only`

For verbose analysis use `convdrift run`, which additionally supports `by-tier` and `full`.

By default, convdrift stores scores in `~/.convdrift/store.sqlite3` and session timelines in `~/.convdrift/sessions/<session_id>.jsonl`. The SQLite store reflects the current computed state; the per-session JSONL timeline is an immutable event log and is not rewritten retroactively after config or scoring changes. Override the store location with `CONVDRIFT_STORE_PATH` only if you have a specific reason to do so.

Each invocation of the statusline script runs a full one-shot analysis and updates the store — no separate process required.

## Notes

- Code formatting is standardized with `ruff`.
- Sidechains are analyzed independently from the mainline conversation.

## References

- https://code.claude.com/docs/en/statusline
