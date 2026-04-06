# convdrift — Roadmap

> This document is a guide, not a contract. Stages, tasks, and priorities should adapt as
> implementation reveals new constraints or opportunities. Mark tasks as they are completed
> or in progress. An agent picking up a task should read DESIGN.md first for full context.

---

## Stack

| Concern | Choice |
|---------|--------|
| Runtime | Python 3.12+ / uv |
| File watching | `watchfiles` |
| CLI | `typer` |
| Score store | `sqlite3` (stdlib) |
| Lexical metrics | `collections` (stdlib) |
| Embeddings (T3) | `sentence-transformers` |
| Testing | `pytest` |

---

## Stage 0 — Foundation

**Goal**: project skeleton, data model, JSONL parser, and episode segmenter working on real transcripts.

**Done when**: given a Claude Code JSONL file, the segmenter outputs a structured list of episodes with message counts and types.

- [x] Initialize uv project (`pyproject.toml`, `uv.lock`, `.python-version`)
- [x] Define core data models: `Message`, `ToolCall`, `ToolResult`, `Episode`
- [x] JSONL reader with tail-follow semantics (emit new lines as file grows)
- [x] Episode segmenter: group messages into episodes (human prompt → next human prompt)
- [x] Sidechain detection: parse `isSidechain: true` messages, keep separate from mainline
- [x] Unit tests using sample transcript fixtures
- [x] `convdrift segment <transcript>` CLI command — prints episode summary

---

## Stage 1 — Tier 1 Signal

**Goal**: M1, M2, M4 computed over a sliding window of episodes; score stored and readable.

**Done when**: `convdrift run <transcript>` prints a Tier 1 score and per-metric breakdown. Score updates as the transcript grows.

- [ ] Implement M1: Tool Error Rate (proportion of `is_error: true` tool results per window)
- [ ] Implement M2: Action Mix (productive / exploratory / recursive distribution)
- [ ] Implement M4: User Message Length Trend (slope over last W episodes)
- [ ] Implement M3: Token Asymmetry Ratio *(stub only — excluded from composite)*
- [ ] Implement M5: Cache Efficiency Drop *(stub only — excluded from composite)*
- [ ] Sliding window engine (default W=5 episodes, configurable)
- [ ] Score smoothing: 3-episode moving average
- [ ] Score store: SQLite schema (`scores`, `metrics`, `sessions` tables)
- [ ] `convdrift run <transcript>` CLI command — live score with per-metric output
- [ ] Tests: known-bad and known-good transcript fixtures produce expected score direction

---

## Stage 2 — Tier 2 + Composite Score

**Goal**: M6 and M7 added; full composite score with configurable weights and thresholds.

**Done when**: `convdrift run` outputs a T1+T2 composite score; weights and thresholds can be overridden via a config file without code changes.

- [ ] Implement M6: Lexical Stagnation Index (trigram overlap across last K assistant text blocks)
- [ ] Implement M7: Correction/Negation Density (multilingual pattern list, configurable)
- [ ] Composite score engine: weighted combination across available tiers
- [ ] Config file (`convdrift.toml`): weights, thresholds, window size, smoothing window
- [ ] Score output formats: `score-only`, `with-metrics`, `by-tier`, `full` (see DESIGN.md)
- [ ] `convdrift config init` — generate default config file
- [ ] Tests: weight overrides produce expected composite changes

---

## Stage 3 — Output Layer

**Goal**: statusline integration and per-session log.

**Done when**: a shell script reads the score store and renders a configurable statusline indicator; session history is queryable after the fact.

- [ ] Statusline shell script (`scripts/statusline.sh`): reads score store, formats output
- [ ] Support display formats: `D:42`, `D:42 [err:0.3 rep:0.6]`, `D:42 T1:38 T2:51`
- [ ] Per-session JSONL log: drift timeline written to `~/.convdrift/sessions/<session_id>.jsonl`
- [ ] `convdrift log <session_id>` — print drift timeline for a past session
- [ ] `convdrift sessions` — list recorded sessions
- [ ] Integration test: run against a live (growing) transcript file end-to-end

---

## Stage 4 — Tier 3 (Embeddings)

**Goal**: M8 and M9 computed via local embeddings; background daemon updates the score store.

**Done when**: daemon runs alongside a live session, enriches the score store with T3 metrics every N new episodes; main score degrades gracefully when daemon is not running.

- [ ] Embedding model integration (`sentence-transformers`, multilingual model)
- [ ] Implement M8: Semantic Orbit Detection (cosine similarity between consecutive episode embeddings)
- [ ] Implement M9: Goal Alignment Score (similarity between last high-level user message and recent output)
- [ ] Daemon process: watches score store for new episodes, computes T3, writes results back
- [ ] Daemon lifecycle: `convdrift daemon start/stop/status`
- [ ] Graceful fallback: T3 weight redistributed to T1/T2 when daemon unavailable
- [ ] Tests: daemon updates score store within expected latency; fallback produces valid score

---

## Stage 5 — Calibration

**Goal**: validate that scores correlate with sessions users perceive as degraded; adjust defaults.

**Done when**: a labeled set of transcripts shows consistent score behavior; default weights updated from empirical findings; at least one task-type baseline profile available.

- [ ] Labeling tool: `convdrift label <transcript>` — annotate episode ranges as healthy / drifting / stuck
- [ ] Calibration script: compare scores against labels, report precision/recall per threshold
- [ ] Collect and label minimum 10 real sessions (mix of healthy and degraded)
- [ ] Task-type baseline profiles: exploratory vs. implementation vs. debugging
- [ ] Update default weights in `convdrift.toml` based on calibration results
- [ ] Document findings: which metrics contributed most, which were noise

---

## Future Work

- Multi-session analysis: drift patterns across sessions in the same project
- Privacy boundaries for non-personal use (transcript retention, embedding storage)
- Sidechain propagation policy: when (if ever) to surface sidechain drift in the mainline score
- API/IPC endpoint for editor integrations
