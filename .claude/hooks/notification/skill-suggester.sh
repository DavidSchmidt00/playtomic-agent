#!/usr/bin/env bash
# Notification hook: suggest relevant skills based on the files being touched.
set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('path', '')))
" 2>/dev/null || echo "")

case "$FILE_PATH" in
  */tools.py)
    echo "💡 Skill tip: consider /test-driven-development before adding new tools." ;;
  */whatsapp/*)
    echo "💡 Skill tip: /requesting-code-review after WhatsApp changes (group-chat edge cases)." ;;
  */web/*)
    echo "💡 Skill tip: /requesting-code-review recommended for frontend changes." ;;
  *pyproject.toml|*.pre-commit-config.yaml|*Dockerfile*)
    echo "💡 Skill tip: /requesting-code-review for infrastructure changes." ;;
esac

exit 0
