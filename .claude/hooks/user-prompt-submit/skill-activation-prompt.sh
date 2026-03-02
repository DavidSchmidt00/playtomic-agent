#!/usr/bin/env bash
# UserPromptSubmit hook: suggest relevant skills based on the user's prompt.
set -euo pipefail

INPUT=$(cat)

PROMPT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('prompt', '') or d.get('user_prompt', '') or d.get('message', ''))
" 2>/dev/null || echo "")

PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

case "$PROMPT_LOWER" in
  *"implement"*|*"add feature"*|*"fix bug"*|*"bugfix"*)
    echo "💡 Skill tip: /test-driven-development — write the test first" ;;
  *"plan"*|*"spec"*|*"requirement"*)
    echo "💡 Skill tip: /writing-plans — plan before touching code" ;;
  *"review"*|*"pull request"*|" *pr #"*)
    echo "💡 Skill tip: /requesting-code-review — verify work before merging" ;;
  *"done"*|*"finish"*|*"complete"*|*"ship"*)
    echo "💡 Skill tip: /finishing-a-development-branch — structured completion options" ;;
  *"refactor"*|*"architect"*|*"clean arch"*|*"hexagonal"*|*"ddd"*)
    echo "💡 Skill tip: /architecture-patterns — Clean/Hexagonal/DDD patterns" ;;
  *"rebase"*|*"cherry-pick"*|*"bisect"*|*"worktree"*|*"reflog"*)
    echo "💡 Skill tip: /git-advanced-workflows — advanced Git operations" ;;
  *"prioriti"*|*"roadmap"*|*"backlog"*|*"rice"*)
    echo "💡 Skill tip: /feature-prioritization-assistant — RICE scoring" ;;
  *"stakeholder"*|*"release note"*|*"announce"*)
    echo "💡 Skill tip: /stakeholder-update-generator — compelling release updates" ;;
  *"okr"*|*"objective"*|*"key result"*)
    echo "💡 Skill tip: /okrs — OKR planning and alignment" ;;
  *"pric"*|*"monetiz"*|*"willingness to pay"*|*"package"*)
    echo "💡 Skill tip: /monetizing-innovation — pricing strategy" ;;
  *"customer interview"*|*"why churn"*|*"jtbd"*|*"jobs to be done"*)
    echo "💡 Skill tip: /jobs-to-be-done — discover unmet needs" ;;
  *"product-market fit"*|*"pmf"*|*"sean ellis"*)
    echo "💡 Skill tip: /pmf-survey — measure product-market fit" ;;
  *"growth loop"*|*"viral"*|*"acquisition"*|*"retention loop"*)
    echo "💡 Skill tip: /growth-loops — design self-reinforcing growth systems" ;;
  *"press release"*|*"working backwards"*|*"pr/faq"*|*"prfaq"*)
    echo "💡 Skill tip: /working-backwards — define product from customer outcome" ;;
  *"decision"*|*"uncertainty"*|*"probabilit"*|*"thinking in bets"*)
    echo "💡 Skill tip: /thinking-in-bets — evaluate decisions on process, not results" ;;
esac

exit 0
