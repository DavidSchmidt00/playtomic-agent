#!/usr/bin/env bash
# PostToolUse hook: log files edited during this session.
# Writes to /tmp/claude-session-changes.log (cleared on system restart).
set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('tool_name', ''))
" 2>/dev/null || echo "")

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('path', '')))
" 2>/dev/null || echo "")

if [[ -n "$FILE_PATH" ]] && [[ "$TOOL_NAME" =~ ^(Edit|Write|MultiEdit|NotebookEdit)$ ]]; then
    echo "$(date '+%H:%M:%S') $TOOL_NAME: $FILE_PATH" >> /tmp/claude-session-changes.log
fi

exit 0
