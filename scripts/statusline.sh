#!/bin/sh
# convdrift statusline script for Claude Code.
#
# Claude Code pipes a JSON object to stdin containing session metadata.
# This script forwards stdin directly to `convdrift statusline-run`,
# which performs one-shot analysis and outputs a compact drift indicator
# (e.g. D:42).
#
# Usage — add to ~/.claude/settings.json:
#   {
#     "statusCommand": "/path/to/convdrift/scripts/statusline.sh"
#   }
#
# Optional env vars:
#   CONVDRIFT_OUTPUT_FORMAT  score-only (default) | with-metrics | by-tier | full
#   CONVDRIFT_STORE_PATH     override the default store path (~/.convdrift/store.sqlite3)

OUTPUT_FORMAT="${CONVDRIFT_OUTPUT_FORMAT:-score-only}"
PROJECT_ROOT="$(dirname "$0")/.."

if [ -n "$CONVDRIFT_STORE_PATH" ]; then
  uv run --project "$PROJECT_ROOT" convdrift statusline-run \
    --output-format "$OUTPUT_FORMAT" \
    --store-path "$CONVDRIFT_STORE_PATH"
else
  uv run --project "$PROJECT_ROOT" convdrift statusline-run \
    --output-format "$OUTPUT_FORMAT"
fi
