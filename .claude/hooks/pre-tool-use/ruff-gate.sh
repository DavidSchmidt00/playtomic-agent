#!/usr/bin/env bash
# Pre-tool-use hook: run ruff on Python files before editing.
# Outputs a warning if lint issues exist — does not block the edit.
set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('path', '')))
" 2>/dev/null || echo "")

if [[ "$FILE_PATH" == *.py ]] && [[ -f "$FILE_PATH" ]]; then
  if ! ruff check "$FILE_PATH" --quiet 2>/dev/null; then
    echo "⚠️  ruff: lint issues found in $FILE_PATH — run 'ruff check --fix $FILE_PATH' to auto-fix" >&2
  fi
fi

exit 0
