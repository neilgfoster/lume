# /iterate [mode]

Main work loop. Drives the current phase forward autonomously.

Modes:
  /iterate              — autonomous, stops only when blocked or phase done
  /iterate supervised   — pauses before each new item for approval
  /iterate spike        — runs next spike item specifically

## The loop

### 1. Orient (read files only — no inference)

Load in order:
1. `.work/phases/phases.json` → current phase number
2. `.work/phases/phase-{N}.json` → goal, DoD, constraints, workstreams
3. `.work/work.json` → active item
4. `.work/session.json` → last session

State out loud (one line each):
- "Phase {N}: {name}"
- "Active: {WORK-XXXX} — {title}"
- "DoD: {X}/{Y} criteria verified"

### 2. Select right tool for item type

```
item.workstream == WS-REQ      → use /requirements pattern
item.workstream == WS-TECH     → use /spike pattern
item.workstream == WS-ARCH     → analysis + structured questions to the operator
item.workstream == WS-PLAN     → synthesise all prior outputs
```

### 3. Work

Execute the item using the right pattern.
Follow phase constraints (check phase file before starting).
Use /stuck after 2 failed attempts.

### 4. Validate (deterministic)

Check each acceptance_criteria item:
- PASS: evidence exists (file exists, command output correct, the operator approved)
- FAIL: specific thing missing
- WAITING: needs operator review — flag and move on

Items requiring operator approval: do not mark complete without explicit "APPROVE".
Present output and wait. Don't loop back — move to next item and return.

### 5. Record (finish-task inline)

Deterministic — do not use inference to assess pass/fail.

a. Run the test suite. Report PASS or FAIL with specific output.
b. Check each `acceptance_criteria` from `.work/work.json` (run a command, check a file). Report PASS or FAIL with evidence.
c. Run `/adversarial-review {task_type}`. Task type: WS-REQ → requirements; WS-ARCH/spike → architecture;
   coding → coding; infra → infra. PASS: proceed. CONDITIONAL: note, proceed, fix before /phase-complete.
   FAIL: fix, retry (max 2 cycles). FAIL×2: surface blocked, wait for human.
d. If all pass: move item from `active` to `completed[]` in work.json, set `status: complete`,
   `completed_date: today`. Update session.json. Git commit: `[WORK-XXXX] title`.

If any fail: list exactly what failed. Do not mark complete. Fix and re-run.

### 6. Decide next

```
All DoD verified?
  → "Phase {N} DoD complete. Run /phase-complete."
  → Stop.

Operator approval pending on any item?
  → List items waiting for review
  → Move to next non-blocked item if one exists

Next item has unmet dependencies?
  → Skip and find next available
  → Flag dependency chain if everything is blocked

Supervised mode?
  → Present next item
  → Wait for go-ahead

Phase AT RISK? (any item blocked >2 sessions)
  → Run /phase-status
  → Ask: "Continue or /change-direction?"
  → Wait.
```

## What /iterate is NOT

Not a planning session. Not a design discussion.
Those happen via natural language: "requirements for X", "spike on Y", "record a decision", "change direction".

If the operator wants to change something mid-iterate: "stop, change direction".


## Adversarial review integration

/iterate automatically triggers adversarial review at the right points:

**After completing each work item (before /finish-task marks done):**
```
Task output ready
  → /adversarial-review {task_type}
  → PASS: proceed to finish-task
  → CONDITIONAL: note, proceed, flag for phase review
  → FAIL: feed findings into refinement, retry (max 2 cycles)
  → FAIL after 2 cycles: surface as blocked, wait for human
```

**Triggered reviews (automatic):**
- Every 10 completed items: /adversarial-review self
- Any task requiring >2 validation loop iterations: /adversarial-review coding/infra
- Any /change-direction: /adversarial-review architecture on the proposed change

**In autonomous mode:**
Claude drives the panel reviews automatically.
Findings and verdicts logged to .work/reviews/{item-id}.json.
Human only sees summary unless verdict is FAIL after 2 cycles.

**In supervised mode:**
Panel findings shown to the operator before proceeding.
The operator can override CONDITIONAL findings (with recorded reason).
The operator cannot override FAIL findings without /change-direction.
