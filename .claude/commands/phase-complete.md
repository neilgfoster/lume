# /phase-complete

Validate the current phase is genuinely done and prepare transition to next phase.

## Step 1 — Validate every Definition of Done criterion

Read `.work/phases/phase-{N}.json` definition_of_done list.

For EACH criterion:
- Find the work item that proves it (from .work/work.json completed items)
- Run a deterministic check where possible (run a command, check output)
- Mark: VERIFIED / UNVERIFIED / FAILED

**Do not proceed if any criterion is UNVERIFIED or FAILED.**
List what's missing and stop.

## Step 2 — Write phase retrospective

Create `.work/decisions/phase-{N}-retro.md` with:

```markdown
# Phase {N} Retrospective — {name}

Date: {today}
Duration: {started} → {today}

## What we built
{list of completed items with one-line descriptions}

## Definition of Done — final status
{each criterion: VERIFIED with evidence}

## Learning goals — what we learned
{each learning goal with actual answer, not "N/A"}

## What surprised us
{anything unexpected that changed how we think about the system}

## What we'd do differently
{honest assessment}

## Direction changes made during this phase
{list from phases.json direction_changes for this phase}

## Impact on next phase
{how learnings should change phase-{N+1} plan}
```

## Step 2.5 — Compute release bump (deterministic)

Run the release calculator for the closing phase:

```bash
python3 .github/scripts/release.py \
  --work-json .work/work.json \
  --phase {N} \
  --current-version $(python3 -c "import json; print(json.load(open('.work/context.json'))['project_version'])")
```

The output JSON contains: `bump` (major/minor/patch), `proposed_version`, and `groups`
(items grouped by `change_class`).

Draft release notes from the groups — the LLM writes prose for each group:
- `breaking` → Breaking Changes
- `feat` → New Features
- `fix` → Bug Fixes
- `chore` → Internal Changes
- `docs` → Documentation

**Present proposed version and release notes to the operator. Wait for approval.**

After approval: update `.work/context.json`:
- Set `project_version` to the approved version.
- Add entry under `releases`: `{"version": "<approved>", "bump": "<bump>", "date": "<today>"}`.

Do NOT update `.work/context.json` until the operator approves the version.

---

## Step 3 — Update next phase based on learnings

Read `.work/phases/phase-{N+1}.json`.

Based on the retro, propose specific changes to:
- definition_of_done (add/remove/change criteria)
- constraints (relax or tighten)
- assumptions_to_validate (mark validated/invalidated, add new ones)

**Present the proposed changes. Wait for approval before writing.**

## Step 4 — After approval, execute transition

1. Update `.work/phases/phase-{N}.json`: set status="complete", completed={today}
2. Update `.work/phases/phase-{N+1}.json`: set status="active", started={today}
3. Update `.work/phases/phases.json`: current_phase={N+1}, log the transition
4. Update `CLAUDE.md`: change current phase section
5. Generate Phase {N+1} work items and add to `.work/work.json`
6. Set active_item to first Phase {N+1} item
7. Git commit: "Phase {N} complete → Phase {N+1}: {name}"

## Step 5 — Announce

Output:
```
╔═══════════════════════════════════════════╗
║  PHASE {N} COMPLETE                       ║
║  → ENTERING PHASE {N+1}: {name}           ║
╚═══════════════════════════════════════════╝

Phase {N} delivered:
  {list of key things built}

Key learnings that shaped Phase {N+1}:
  {list of 2-3 most important learnings}

First task: {WORK-XXXX}: {title}

Run /start-session to begin.
```


## Adversarial phase review (required before transition)

Before validating DoD criteria, convene the phase review panel:

```
/adversarial-review phase
```

Phase review panel (see docs/review-panels.md):
  Core (named agents): scope-auditor, historian, existential-challenger (mandatory at /phase-complete per ADR-013)
  From reference library: evidence-checker, assumption-challenger
  Optional from reference library: devil-advocate or new-engineer

Load reference-library agents from `skill/hedl/references/review-library.md`
and pass their prompts as system prompts to sub-agent calls.

This review is MORE thorough than task-level review.
It looks at the phase as a whole:
- Were all DoD criteria genuinely met or just technically met?
- Were assumptions validated or just assumed validated?
- Was anything quietly dropped that should have been recorded?
- Do the phase outputs actually support Phase {N+1} starting?
- Are there conditional findings from task reviews that were never fixed?

**Phase transition is blocked if phase adversarial review returns FAIL.**

If CONDITIONAL: fix all conditional findings before transition.
If PASS: proceed to DoD verification (Step 1 above).

Include phase review verdict in the retrospective document.
