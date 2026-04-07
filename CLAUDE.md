# convdrift

Session stagnation and looping detection for human-LLM coding sessions.

## Language Policy

- All code, documentation, and comments must be written in **English**.
- Conversations with the assistant continue in **Spanish**.

## Project State

- Phase: Stage 3 complete (output layer)
- Stages 0–3 implemented; Stage 4 (embeddings/daemon) and Stage 5 (calibration) pending
- See DESIGN.md for the full proposal, problem definition, metrics, and architecture
- See ROADMAP.md for implementation stages

## Key Concepts

- Analyzes Claude Code JSONL transcripts in real time (tail-follow semantics)
- Unit of analysis: **episode** (one human prompt + all resulting assistant/tool turns)
- Produces a Drift Score (0–100) from 3 metric tiers:
  - Tier 1: structural (tool error rate, action mix, token asymmetry*, cache efficiency*)
  - Tier 2: lexical (lexical stagnation index, correction marker rate)
  - Tier 3: semantic (semantic orbit detection*, goal alignment)
  - *experimental metrics
- Score degrades gracefully: Tier 1 alone produces a useful signal
- Output: composite score + per-metric breakdown; statusline script chooses what to display. Session timelines are immutable event logs; the SQLite store is the current recomputed state.

## Architecture

- Input: JSONL transcript via `transcript_path`
- Episode segmenter: groups raw messages into episodes before analysis
- Fast path (T1+T2): sub-second, sliding window over last W episodes
- Slow path (T3): background daemon with embeddings, triggered every N episodes
- Score smoothing: moving average over last 3 episodes to prevent statusline jitter
- Score store: SQLite with WAL mode at `~/.convdrift/store.sqlite3`; session timelines at `~/.convdrift/sessions/<session_id>.jsonl`
- Primary runtime: `statusline-run` — invoked as Claude Code `statusCommand`, one-shot analysis + store update + indicator output per refresh. No separate process required.
- `run --follow`: opt-in long-running watcher for manual monitoring or debugging

## Design Principles

- Non-invasive: read-only access to transcripts
- Information only: reports signals, does not execute actions
- Configurable: weights, thresholds, window size, and output format have sensible defaults but are user-configurable
- Stack-agnostic: DESIGN.md does not prescribe implementation technologies
- Multilingual: handles mixed-language conversations

## Open Questions (see DESIGN.md)

- Ground truth: how to validate score correlation with perceived degradation
- Task-type calibration: per-task baseline profiles vs. manual threshold configuration
- Sidechain propagation: independent analysis vs. parent signal propagation
- Privacy boundaries for non-personal use
