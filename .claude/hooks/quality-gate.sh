#!/usr/bin/env bash
# Runs the CLAUDE.md quality gates after an edit to nj/ or tests/.
#
# CLAUDE.md requires ruff and pytest to run after touching those trees. Relying
# on the assistant to remember is how a regression like the prep_v1 NameError
# ships; this makes it mechanical.
#
# Advisory, not blocking: mid-refactor states legitimately fail, and blocking
# there would be worse than useless. Failures are surfaced back to the model via
# systemMessage so they get fixed in the same turn.
#
# Reads the PostToolUse payload on stdin. Exits 0 always.

set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

payload="$(cat)"
file="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)"

# Only Python under nj/ or tests/ is in scope.
case "$file" in
  "$repo"/nj/*.py | "$repo"/tests/*.py) ;;
  *) exit 0 ;;
esac

cd "$repo" || exit 0

report() {
  # jq -Rs turns the raw text into a JSON string safely.
  printf '%s' "$1" | jq -Rs '{
    systemMessage: ("nj-cli quality gate failed — fix before continuing:\n" + .),
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: ("The CLAUDE.md quality gate failed after your edit:\n" + .)
    }
  }'
  exit 0
}

if ! lint="$(poetry run ruff check nj/ tests/ 2>&1)"; then
  report "$lint"
fi

if ! fmt="$(poetry run ruff format --check nj/ tests/ 2>&1)"; then
  report "$fmt"
fi

if ! tests="$(poetry run pytest tests/ -q --no-header -p no:cacheprovider 2>&1)"; then
  # The tail is what matters; the full log would swamp the context.
  report "$(printf '%s' "$tests" | grep -E '^(FAILED|ERROR)|failed|passed' | tail -20)"
fi

exit 0
