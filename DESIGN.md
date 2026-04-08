# convdrift

Session stagnation and looping detection for human-LLM coding sessions.

## What is convdrift?

convdrift analyzes human-LLM conversation transcripts to produce a quality signal — an interpretable number that rises when a session is becoming stuck and falls when it is making progress.

**Target v1**: Claude Code sessions. The design is applicable to any structured conversation transcript.

**Thesis**: The gap between "how much context have I used" and "is this conversation still producing value" is the gap convdrift fills. The tool delivers information — what to do with that information is the user's or agent's decision.

---

## The Problem

Human-LLM sessions degrade in observable ways:

1. **Circular reasoning** — The assistant revisits the same concepts, files, or approaches without forward progress.
2. **Escalating re-explanation** — The user's messages grow longer as they attempt to clarify what the assistant misunderstands.
3. **Tool error cascades** — The assistant retries failing operations with minor variations. The error rate climbs.
4. **Verbose non-output** — Long responses but no files written, no code edited, no commits made.
5. **Semantic stagnation** — Vocabulary and concepts stop changing. Same terminology, same problem, from different angles.

**Root causes**:
- **Context dilution** — Early context competes with recent but less relevant material. Effective attention on the original goal diminishes.
- **Goal drift** — Multi-step tasks accumulate ambiguity. Each turn can introduce small misalignments that compound.
- **Error compounding** — A failed tool call generates a recovery attempt that consumes context without advancing the goal.

---

## Why It Matters

- In long sessions (observed: 96,000+ context tokens over 58 assistant messages), there is no signal telling the user "this conversation is stuck."
- Existing tools show token usage, cost, and rate limits — all consumption metrics, none about value.
- Users currently rely on gut feeling to decide when to start a new session or change approach. That gut feeling is what convdrift formalizes.

---

## Available Data

Claude Code sessions produce a JSONL file (one JSON object per line) accessible via `transcript_path`.

### User messages
- Plain text (human input) or arrays containing `tool_result` objects
- `tool_result.is_error`: boolean — direct signal of tool failure
- ISO 8601 timestamps, `parentUuid` for chain reconstruction

### Assistant messages
- Text blocks: full assistant prose, analyzable
- Tool use blocks: tool `name` (Read, Write, Edit, Bash, Glob, Grep, Agent, etc.) and `input`
- Thinking blocks: encrypted — only a signature is stored, **not analyzable**
- Usage metadata: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- `stop_reason`: `end_turn` or `tool_use`

### System messages
- `durationMs`: wall-clock time per turn
- `messageCount`: cumulative count
- Local command results: stdout, stderr, return code

### Other
- File history snapshots with timestamps
- Subagent messages: `isSidechain: true` with `agentId`
- Session metadata: git branch, working directory, version, permission mode

### Not available
- Thinking block content (encrypted)
- System prompts
- Internal model state

---

## Unit of Analysis: The Episode

The fundamental unit of analysis is the **episode**: one human message plus all resulting assistant messages and tool calls until the next human message.

Analysis does not operate at the individual message level. Reason: a single user action can generate dozens of messages (tool calls, results, continuations). Message-level analysis produces extremely noisy signals. The episode maps to "one unit of intent and response."

The sliding window operates over the last **W episodes** (default: 5, configurable).

Sidechains (`isSidechain: true`) are analyzed independently. Their drift does not propagate automatically to the parent — they are exposed as a separate signal.

---

## Metrics

Organized by computational cost. Each tier adds resolution to the signal.

### Tier 1: Structural (sub-second, JSONL parsing only)

**M1. Tool Error Rate**
Proportion of `tool_result` messages with `is_error: true` in the last W episodes.
Range: 0.0 (no errors) to 1.0 (all errors). The most direct signal available.

**M2. Action Mix**
Distribution of the assistant's tool calls within the window:
- Productive: Write, Edit, NotebookEdit, Bash with write-effect commands (`git commit`, `git push`, redirects, etc.)
- Exploratory: Read, Glob, Grep, Bash with read-only commands
- Recursive: Agent (complexity escalation)
- Neutral: Bash with build/test/run commands (`pytest`, `make`, `uv run`, `npm test`, `cargo build`, etc.) — not counted toward drift pressure

Reported as a distribution, not as a binary score. The drift signal uses `exploratory + recursive` as pressure; neutral commands are excluded. High exploratory ratio is normal at the start of a task; problematic if it persists when output would be expected.

**M3. Token Asymmetry Ratio** *(experimental)*
`output_tokens / (input_tokens + cache_read_input_tokens)` averaged over the window. Disproportionately high ratio suggests over-explanation or hedging. Weak signal on its own — include only if empirically validated.

**M4. User Message Length Trend**
Slope of user text message lengths (excluding automated tool results) over the last W episodes. An upward trend indicates the user is re-explaining.

**M5. Cache Efficiency Drop** *(experimental)*
`cache_read / (cache_read + cache_creation + input_tokens)` per assistant message. A sudden drop may indicate context eviction. Causal correlation with degradation is unvalidated — include as a secondary indicator.

### Tier 2: Lexical (lightweight text processing)

**M6. Lexical Stagnation Index**
N-gram overlap (bigrams or trigrams) between the last K assistant text blocks. High overlap indicates the conversation is repeating the same content. Fast-path implementation of stagnation detection.

**M7. Correction Marker Rate**
Proportion of user messages in the window containing correction markers: "no", "that's wrong", "not what I meant", "again", "I already told you". Most direct signal of user dissatisfaction. Must support multilingual patterns.

### Tier 3: Semantic (embedding computation, asynchronous)

**M8. Semantic Orbit Detection** *(experimental)*
Cosine similarity between embedding vectors of assistant text blocks in consecutive episodes. Sustained high similarity (>0.85) indicates the conversation is covering the same semantic ground. Slow-path implementation of stagnation detection.

**M9. Goal Alignment Score**
Cosine similarity between the embedding of the user's most recent high-level message and the assistant's recent output. Measures whether the conversation still addresses what the user is currently asking for.

**Note**: M8 and M6 measure the same phenomenon (stagnation) at different tiers. M6 is the fast approximation; M8 is the semantic refinement. They are not redundant — they are the same indicator at different resolutions.

### Discarded metrics

The following were evaluated and excluded:

| Metric | Reason |
|--------|--------|
| Turn Duration | Too many external variables (network, provider load, local CPU) contaminate the signal |
| Question Density | Clarifying questions can be correct agent behavior, not a failure signal |
| Vocabulary Saturation | Redundant with M6; focused technical conversations naturally reuse vocabulary |
| Semantic Progress Rate | Embedding centroid motion is too abstract to be actionable |

---

## Composite Score: The Drift Score

A single normalized value (0–100) combining metrics from available tiers.

### Default weights

| Tier | Default weight | Availability |
|------|---------------|-------------|
| Tier 1 (structural) | 50% | Always |
| Tier 2 (lexical) | 30% | With text processing |
| Tier 3 (semantic) | 20% | With embeddings daemon |

**Weights are configurable.** Defaults are a reasonable starting point, not scientifically calibrated values. Users with context about their work style or task type can adjust them.

The score degrades gracefully — if only Tier 1 is available, it uses only those metrics and still produces a useful number.

### Interpretation

| Range | Meaning |
|-------|---------|
| 0–25 | Healthy. Forward progress, low error rate, productive output. |
| 25–50 | Mild drift. Some repetition or exploration without output. Consider refocusing. |
| 50–75 | Significant drift. Multiple degradation signals active. Course correction recommended. |
| 75–100 | Critical drift. Session is stuck or producing little value. Consider starting a new session. |

Thresholds are configurable.

### Score output

The system exposes both the composite score and individual per-metric values. Two output contracts exist, one per command family:

**`statusline-run` / `statusline`** — compact indicator for real-time display:
- `score-only` (default with config): `D:42`
- `with-metrics` (default without config): `Mild drift 42 | errors 30%`

**`run`** — verbose analysis for manual inspection:
- `score-only`: `D:42`
- `with-metrics`: `Mild drift 42 | errors 30%`
- `by-tier`: `D:42 Str:38 Lex:51`
- `full` (default): score band, window, diagnosis, per-signal breakdown, action mix, technical detail

---

## Architecture

```
+----------------+    +------------+    +----------+    +---------+    +---------+
| JSONL          | -> | Episode    | -> | Analysis | -> | Score   | -> | Outputs |
| Transcript     |    | Segmenter  |    | Pipeline |    | Store   |    |         |
| (live file)    |    +------------+    +----------+    +---------+    +---------+
                                             |
                                       +-----+-----+
                                       |           |
                                 +---------+  +-----------+
                                 | Fast    |  | Slow      |
                                 | Path    |  | Path      |
                                 | (T1+T2) |  | (T3)      |
                                 +---------+  +-----------+
```

### Input layer
- Reads the JSONL file identified by `transcript_path`
- Handles the file growing in real time (tail-follow semantics)
- Does not lock or interfere with the writing process
- Parses line-by-line; each line is an independent JSON object

### Episode segmenter
- Groups raw messages into episodes (human prompt + all resulting messages until the next human prompt)
- Separates sidechains from the mainline conversation
- Emits complete episodes to the analysis pipeline — **not individual messages**

### Analysis layer — Fast path
- Computes Tier 1 and Tier 2 metrics over the last W episodes
- Sliding window, not full transcript
- Sub-second completion
- Triggered on complete episode, not on individual message

### Analysis layer — Slow path
- Computes Tier 3 metrics using an embedding model
- Separate process/daemon
- Triggered every N new episodes, not every message
- Writes results to Score Store asynchronously

### Score store
- Simple file-based or in-memory store
- Contains: composite score, per-metric values, timestamp, window parameters, active tiers
- Readable by multiple consumers without locking
- Includes `freshness` field: when each tier was last updated

### Score smoothing
- The score published to the Score Store is a moving average over the last 3 episodes
- Goal: prevent jitter in the statusline during active tool sequences
- Configurable: smoothing window can be reduced to 1 (no smoothing) for retrospective use

### Output layer

**Primary runtime — `statusline-run`**
The main Claude Code integration entrypoint. Invoked as `statusCommand` in `~/.claude/settings.json`. Receives a JSON object on stdin from Claude Code (containing `transcript_path`), runs a one-shot T1+T2 analysis, updates the score store and session log, prints a compact indicator (e.g., `Mild drift 42 | errors 30%`), and exits. No separate process required. Supports `score-only` and `with-metrics` formats only; defaults to `with-metrics`.

Internally uses the same fast-path pipeline as `run`. Incremental checkpointing may be added later if profiling shows one-shot is too slow for long sessions — without changing the user-facing `statusCommand` configuration.

**Secondary commands**
- **`run --follow`**: long-running watcher for manual monitoring or debugging. Not required for normal statusline use.
- **`statusline`**: read-only store query, formats indicator from last persisted snapshot. Useful when `run --follow` is active separately.
- **Log/history**: per-session drift timeline for retrospective analysis
- **API/IPC**: for editors, dashboards, or other tools

---

## Use Cases

**Real-time statusline indicator**
While working in Claude Code, the statusline shows `D:23` (healthy) or `D:78` (stuck). The user sees at a glance whether to continue, refocus, or start a new session.

**Session retrospective**
After a session, review the drift timeline. Identify which turns caused degradation. Learn patterns: "vague instructions increase drift; specific file references keep it low."

**Conversation quality benchmarking**
Compare drift profiles across models, effort levels, or task types. Answer: "Does Opus maintain lower drift than Sonnet on refactoring tasks?"

**Degradation taxonomy (research)**
Build a dataset of (transcript, drift_scores) to study which conversation structures lead to degradation.

**Multi-session analysis**
Track drift across sessions in the same project. Detect patterns: "third session on this refactoring always degrades past episode 20."

---

## Design Principles

1. **Graceful degradation** — Produces useful output with only Tier 1 metrics. Each additional tier refines but is not required.
2. **Non-invasive** — Reads transcripts. Never writes to them, modifies the LLM's behavior, or intercepts communication.
3. **Information only** — convdrift reports; it does not execute actions. Decisions (compact, restart, change prompt) belong to the user or the agent.
4. **Episode-based** — Metrics operate on complete episodes, not individual messages. Keeps computation stable and scores interpretable.
5. **Window-based** — Sliding window over recent episodes, not full history. Keeps computation bounded and focused on current state.
6. **Interpretable over precise** — A score of 67 doesn't need mathematical certainty. It needs to correlate with the human's intuition of "stuck." Actionability over precision.
7. **Configurable** — Weights, thresholds, window size, and output format are configurable. Defaults are a reasonable starting point.
8. **Language-aware** — Handles multilingual conversations. Tier 1 is language-independent. Tier 2 supports multilingual patterns. Tier 3 embeddings handle it naturally.

---

## Known Failure Modes

Situations where the score will produce false positives or misleading signals:

- **Legitimate exploration**: an active research session naturally has high lexical repetition and low write ratio. That is not drift — it is the task type.
- **User-initiated goal change**: if the user changes direction, M9 (Goal Alignment) will spike. This is not a model failure.
- **Hidden internal reasoning**: the model may be "orbiting" in its thinking blocks while producing superficially varied tool calls. convdrift cannot see this.
- **Window sensitivity**: window too small → a single retry looks like 100% error rate. Window too large → misses the start of a spiral. Default W=5 episodes is an initial balance.
- **Model and environment variance**: metrics may behave differently across model versions, permission modes, and tool availability.
- **Pasted agent output in user messages**: when a user copies another agent's response (e.g. Codex output) and pastes it into the conversation, the resulting user message is very long and may contain words that match correction patterns. This inflates both `user_message_length_trend_score` and `correction_marker_rate`. No automatic fix exists without heuristics that risk new false positives. Expected to surface naturally during Stage 5 labeling.

---

## Open Questions

1. **Ground truth**: How to validate that the score correlates with sessions users perceive as degraded? Labeled sessions are needed to calibrate weights and thresholds empirically rather than arbitrarily.

2. **Task-type calibration**: exploratory, refactoring, debugging, and implementation tasks have different normal drift profiles. Does the tool support per-task-type baseline profiles, or does it require users to configure thresholds manually?

3. **Sidechains**: Are subagents analyzed only independently, or should a sidechain signal propagate to the parent (e.g., a critically drifting sidechain as a warning in the mainline)?

4. **Privacy**: The tool reads full conversation content. For use beyond personal, what are the boundaries for transcript retention and processing?
