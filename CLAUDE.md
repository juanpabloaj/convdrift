# convdrift

Session stagnation and looping detection for human-LLM coding sessions.

## Language Policy

- All code, documentation, and comments must be written in **English**.
- Conversations with the assistant continue in **Spanish**.

## Project State

- Phase: design complete, pre-implementation
- See DESIGN.md for the full proposal, problem definition, metrics, and architecture

## Key Concepts

- Analyzes Claude Code JSONL transcripts in real time (tail-follow semantics)
- Unit of analysis: **episode** (one human prompt + all resulting assistant/tool turns)
- Produces a Drift Score (0–100) from 3 metric tiers:
  - Tier 1: structural (tool error rate, action mix, token asymmetry*, cache efficiency*)
  - Tier 2: lexical (lexical stagnation index, correction density)
  - Tier 3: semantic (semantic orbit detection*, goal alignment)
  - *experimental metrics
- Score degrades gracefully: Tier 1 alone produces a useful signal
- Output: composite score + per-metric breakdown; statusline script chooses what to display

## Architecture

- Input: JSONL transcript via `transcript_path`
- Episode segmenter: groups raw messages into episodes before analysis
- Fast path (T1+T2): sub-second, sliding window over last W episodes
- Slow path (T3): background daemon with embeddings, triggered every N episodes
- Score smoothing: moving average over last 3 episodes to prevent statusline jitter
- Score store: file-based, readable without locking, includes per-tier freshness

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
