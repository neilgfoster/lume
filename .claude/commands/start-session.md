# /start-session

The SessionStart hook runs `.claude/startup.sh` automatically — its output is already
visible. This command provides the same orientation on demand.

1. Read CLAUDE.md — confirm you understand the current phase
2. Read the active work item from .work/work.json
3. State out loud: "I am working on [WORK-XXXX]: [title]. The acceptance criteria are: [list]"
4. Do not begin coding until you have stated the above

If startup.sh output is missing, read these files in order:
1. CLAUDE.md
2. .work/work.json (active item only)
3. .work/session.json

Do not summarise the project. Do not make a plan. Just confirm the active task and start.
