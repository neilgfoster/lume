#!/bin/bash
# .claude/startup.sh
# Run at the start of every Claude Code session
# Goal: orient Claude in <1000 tokens

PROJECT_NAME=$(python3 -c "import json; print(json.load(open('.work/context.json'))['meta'].get('project','PROJECT'))" 2>/dev/null || echo "PROJECT")
echo "╔═══════════════════════════════════════╗"
printf "║  %-36s ║\n" "$PROJECT_NAME — SESSION START"
echo "╚═══════════════════════════════════════╝"
echo ""


# Project state
echo "▶ PHASE $(cat .work/context.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['meta']['phase'])" 2>/dev/null || echo '0')"
echo ""

# Active work item
echo "▶ ACTIVE TASK"
python3 -c "
import json
with open('.work/work.json') as f:
    d = json.load(f)
active_id = d['meta'].get('active_item')
for item in d.get('active', []):
    if item['id'] == active_id:
        print(f\"  {item['id']}: {item['title']}\")
        print(f\"  Status: {item['status']}\")
        print(f\"  Acceptance criteria:\")
        for c in item['acceptance_criteria']:
            print(f\"    - {c}\")
" 2>/dev/null || echo "  No active item — check .work/work.json"
echo ""

# Last session
echo "▶ LAST SESSION"
python3 -c "
import json
with open('.work/session.json') as f:
    d = json.load(f)
print(f\"  Date: {d.get('date', 'unknown')}\")
completed = d.get('completed', [])
if completed:
    print(f\"  Completed: {', '.join(completed)}\")
else:
    print('  Completed: nothing yet')
if d.get('blockers'):
    print(f\"  Blockers: {', '.join(d['blockers'])}\")
print(f\"  Next: {d.get('next_item', 'check work.json')}\")
" 2>/dev/null || echo "  No session history"
echo ""

# Backlog summary
echo "▶ BACKLOG"
python3 -c "
import json
with open('.work/work.json') as f:
    d = json.load(f)
backlog = d.get('backlog', [])
for item in backlog[:5]:
    deps = ', '.join(item.get('dependencies', [])) or 'none'
    print(f\"  {item['id']}: {item['title']} [deps: {deps}]\")
if len(backlog) > 5:
    print(f\"  ... and {len(backlog)-5} more\")
" 2>/dev/null
echo ""

echo "▶ REMINDER: One task at a time. Run /finish-task before starting next."
echo "══════════════════════════════════════════"
