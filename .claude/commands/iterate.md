# /iterate [mode]

Main work loop. Drives the active work item from implementation all the way
through to an operator-ready PR, then stops for operator review at merge time.
The steps between implementation and PR-raised are mechanical (Principle 1:
deterministic over inference), so /iterate carries through them rather than
handing back at "implementation done".

Modes:
  /iterate              — autonomous; drives the item to a merge-ready PR, then stops
  /iterate supervised   — pauses at each checkpoint (item start, gate result,
                          review verdict, fix-cycle outcome) for approval
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
d. If all pass: commit the implementation on the branch (`[WORK-XXXX] title`).
   Do NOT mark the item completed here — the `active` -> `completed` transition is
   recorded at the operator-ready stop point in step 6, folded into the delivering
   PR (standards.md). Deferring it means a stuck PR never leaves a falsely-completed
   item, and the item is completed on `main` only when that PR merges.

If any fail: list exactly what failed. Do not mark complete. Fix and re-run.

### 6. Drive to an operator-ready PR

Implementation done does not end /iterate. On the same branch, run the `/pr-ready`
controller loop (`skill/hedl/commands/pr-ready.md`), which owns the canonical steps
and the stop condition from local gate through operator handoff. These steps need
no operator judgement, so /iterate carries through them.

Autonomous precondition (ADR-025): before driving to PR unsupervised, assert that
branch protection is active on the base branch — it is the structural enforcement
of the operator's sole checkpoint (e.g. `gh api repos/{owner}/{repo}/branches/main/protection`).
If it cannot be confirmed, degrade to supervised (pause for operator approval at
the handoff); never rely on the protection being there by convention.

The adversarial review from step 5c stands as the PR-diff review unless a fix
cycle adds commits after it — then pr-ready re-runs the review on the updated diff.

Sequencing the completion record: once the gate is green, adversarial review is
resolved, and no fixes remain pending, make the `active` -> `completed` transition
(with `completed_date`) plus the session.json update the FINAL commit on the branch
(folded into the PR), then push and let CI run on that commit. The green CI on this
final commit is what establishes merge-ready — so the operator sees green on the
exact state that will merge, with no later commit reopening it. Then report and
stop. Never merge — the merge is the operator's checkpoint.

If pr-ready escalates via `/stuck` (a BLOCKING finding or red CI unresolved after
its 3-cycle limit): the item is NOT done. Leave it `active`, surface it as blocked,
and wait for the operator. Do not record it completed.

Supervised mode: pause at the checkpoints named in the Modes section (gate result,
review verdict, each fix-cycle outcome) in addition to the intra-implementation
checkpoints; the pauses extend through this range, they are not stripped.

### 7. Decide next

Raising the PR (or surfacing a `/stuck` block) ends this invocation. Report the
outcome — PR state (checks, review verdict, open threads), or the blocker — and
stop. Do not auto-start the next item; it may depend on this PR merging, which is
operator-gated.

The selection logic below runs at the START of the NEXT /iterate invocation
(steps 1-2), once the prior PR has merged — not in the same turn the PR was raised:

```
All DoD verified?
  → "Phase {N} DoD complete. Run /phase-complete." → Stop.

Next item has unmet dependencies?
  → Skip and find next available; flag the chain if everything is blocked.

Supervised mode?
  → Present the selected item and wait for go-ahead before implementing.

Phase AT RISK? (any item blocked >2 sessions)
  → Run /phase-status; ask "Continue or /change-direction?"; wait.
```

## What /iterate is NOT

Not a planning session. Not a design discussion.
Those happen via natural language: "requirements for X", "spike on Y", "record a decision", "change direction".

If the operator wants to change something mid-iterate: "stop, change direction".


## Adversarial review integration

/iterate automatically triggers adversarial review at the right points:

**Per item, at step 5c (before the item is recorded complete in step 6):**
```
Task output ready
  → /adversarial-review {task_type}
  → PASS: proceed
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
Once it passes, /iterate continues into step 6 (the pr-ready loop).

**In supervised mode:**
Panel findings shown to the operator before proceeding.
The operator can override CONDITIONAL findings (with recorded reason).
The operator cannot override FAIL findings without /change-direction.
