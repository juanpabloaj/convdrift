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

- [x] Implement M1: Tool Error Rate (proportion of `is_error: true` tool results per window)
- [x] Implement M2: Action Mix (productive / exploratory / recursive distribution)
- [x] Implement M4: User Message Length Trend (slope over last W episodes)
- [x] Implement M3: Token Asymmetry Ratio *(stub only — excluded from composite)*
- [x] Implement M5: Cache Efficiency Drop *(stub only — excluded from composite)*
- [x] Sliding window engine (default W=5 episodes, configurable)
- [x] Score smoothing: 3-episode moving average
- [x] Score store: SQLite schema (`scores`, `metrics`, `sessions` tables)
- [x] `convdrift run <transcript>` CLI command — live score with per-metric output
- [x] Tests: known-bad and known-good transcript fixtures produce expected score direction

---

## Stage 2 — Tier 2 + Composite Score

**Goal**: M6 and M7 added; full composite score with configurable weights and thresholds.

**Done when**: `convdrift run` outputs a T1+T2 composite score; weights and thresholds can be overridden via a config file without code changes.

- [x] Implement M6: Lexical Stagnation Index (trigram overlap across last K assistant text blocks)
- [x] Implement M7: Correction Marker Rate (multilingual pattern list, configurable)
- [x] Composite score engine: weighted combination across available tiers
- [x] Config file (`convdrift.toml`): weights, thresholds, window size, smoothing window
- [x] Score output formats: `score-only`, `with-metrics`, `by-tier`, `full` (see DESIGN.md)
- [x] `convdrift config init` — generate default config file
- [x] Tests: weight overrides produce expected composite changes

---

## Stage 3 — Output Layer

**Goal**: Claude Code statusline integration and per-session log.

**Done when**: `convdrift statusline-run` is configured as `statusCommand` in `~/.claude/settings.json`, updates the store on each refresh, and renders a configurable drift indicator with no separate process required; session history is queryable after the fact.

- [x] Per-session JSONL log: drift timeline written to `~/.convdrift/sessions/<session_id>.jsonl`
- [x] `convdrift log <session_id>` — print drift timeline for a past session
- [x] `convdrift sessions` — list recorded sessions
- [x] `convdrift statusline` — read-only store query for power users / debugging
- [x] Support display formats for `statusline`/`statusline-run`: `score-only` (`D:42`), `with-metrics` (`Mild drift 42 | errors 30%`)
- [x] Integration test: run against a live (growing) transcript file end-to-end
- [x] `convdrift statusline-run` — one-shot Claude Code integration: reads stdin JSON, analyzes transcript, updates store, prints indicator, exits
- [x] `scripts/statusline.sh` updated: forwards Claude Code stdin to `statusline-run`
- [x] Tests: `statusline-run` invoked with a JSON stdin payload produces correct output and updates store

---

## Stage 3.5 — Pre-Stage 4 Hardening

**Goal**: resolve known metric inaccuracies and runtime risks before adding embedding complexity.

**Done when**: latency is measured and either accepted or mitigated; M2 and M6 fixes are shipped; JSONL timeline semantics are documented; M7 rename is complete.

- [x] **Latency audit**: benchmarked on 4–57 episode transcripts; p99 ≤ 180 ms (dominated by `uv run` startup, not computation); incremental checkpointing not needed at current scale
- [x] **M2 fix**: add `NEUTRAL_BASH_PREFIXES` for build/test/run commands (`make`, `uv run`, `npm test`, `cargo build`, `pytest`, etc.); add `neutral` field to `ActionMix`; change `_classify_bash_call` fallback from `"exploratory"` to `"neutral"`; exclude `neutral` from drift score
- [x] **M6 fix**: replace `[a-z0-9_]+` with `\w+` in `_extract_ngrams` so accented and non-ASCII tokens are not silently dropped before n-gram computation
- [x] **M7 rename**: rename `correction_density` → `correction_marker_rate` throughout metrics, scoring, store, history, statusline, cli, and tests
- [x] **JSONL timeline semantics**: document `append_session_timeline` as immutable event log (scores at time of computation, not recomputed)
- [x] **M2 unknown-tool fallback**: change `_classify_tool_call` fallback for unrecognized non-Bash tools (MCP tools, custom tools) from `"exploratory"` to `"neutral"`; add unit test
- [x] **Output UX**: `with-metrics` statusline shows `"Healthy 19 | errors 33%"` (human labels, %, signals above 0.20 threshold, top 2 only); `run --full` adds `Diagnosis:` line (strongest signal) and human-readable `Signals:` section with percentages; `statusline-run` / `statusline` restricted to `score-only` and `with-metrics` (default `with-metrics`)
- [ ] **Real-session validation**: run `statusline-run` on 2–3 real Claude Code sessions; verify score direction matches perceived session quality; note any obvious false positives
- [ ] **M4 normalization** *(low priority — may defer to Stage 5)*: evaluate whether dividing slope by `average_length` vs `max_length` better captures re-explanation signal; update `_normalize_positive_trend` if a clearly better formula is found

---

## Stage 4 — Tier 3 (Embeddings)

**Goal**: M8 and M9 computed via local embeddings; background daemon updates the score store.

**Done when**: daemon runs alongside a live session, enriches the score store with T3 metrics every N new episodes; main score degrades gracefully when daemon is not running.

### Design phase (complete before implementation)

- [ ] **Daemon runtime model**: decide between persistent user-level process, per-session process, or opportunistic worker launched by CLI; document decision in DESIGN.md
- [ ] **Coordination with `statusline-run`**: define whether `statusline-run` only reads pre-computed T3 from the store, can trigger pending work, or has no interaction with the daemon beyond shared SQLite; document in DESIGN.md
- [ ] **SQLite write/read semantics**: define which process owns which tables, how pending work is identified, and how to prevent race conditions or duplicate computation; document in DESIGN.md
- [ ] **Failure model**: define behavior when daemon is absent, crashes, falls behind, or cannot load the embedding model; T1+T2 score must continue unaffected; document in DESIGN.md
- [ ] **Packaging**: add `sentence-transformers` as an optional dependency (`[embeddings]` extras group in `pyproject.toml`); T3 path raises a clear error if the extra is not installed

### Implementation

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
