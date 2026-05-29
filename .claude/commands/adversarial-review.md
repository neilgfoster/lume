# /adversarial-review [task-type] [scope]

Convene a multi-agent adversarial review panel.
Personas are selected based on task type.
Reviews are parallel. Findings are rebuttable. Verdict is structured.

## Usage

```bash
/adversarial-review coding          # review current coding task output
/adversarial-review infra           # review current infra task output
/adversarial-review architecture    # review an ADR or design decision
/adversarial-review requirements    # review a requirements document
/adversarial-review phase           # phase completion review
/adversarial-review self            # the project reviewing itself
/adversarial-review <task-type> <file-or-scope>  # specific target
```

## Step 1 — Select panel

**When a git diff is available** (reviewing a PR, branch, or code change):

Invoke the `review-dispatcher` sub-agent. Pass it the diff and PR description.
Use the dispatcher's `RUN` list as the panel. The dispatcher is the authoritative
selector for diff-based reviews — it reads what actually changed, not just the
declared task type.

After the dispatcher responds, if `.github/scripts/am_i_done.py` exists, validate with:
```bash
python3 .github/scripts/am_i_done.py --check dispatch --panel agent1,agent2,...
```
If validation exits non-zero, add the missing mandatory agents.
(Skip this step if the script is not present.)

**When no diff is available** (reviewing a doc, spec, or design by path):

Read `docs/review-panels.md` and select personas based on its
"Panel by task type" table:

- All required personas
- One optional persona (select most relevant to current context)

State: "Panel convened: [Persona A], [Persona B], [Persona C], [Synthesis]"

## Step 2 — Brief each persona

For each persona, construct a targeted system prompt:

```text
You are {persona.name}.
Your goal: {persona.goal}
Your approach: {persona.approach}
You are reviewing: {what is being reviewed}
You are NOT trying to be helpful. You are trying to find problems.
The burden of proof is on the work, not on you.

For each finding, output a JSON object matching your agent schema exactly.
Severity must be one of: BLOCKING, SIGNIFICANT, MINOR.
Every finding must have a non-empty evidence field naming a file:line, ADR, or specific reference.
Vague concerns without evidence are not findings — omit them.

Output a JSON array of finding objects. No preamble. No summary.
```

## Step 3 — Run panel (parallel)

Invoke each persona simultaneously (separate API calls, same content).
Each persona reviews independently without seeing others' findings.
Collect all findings.

## Step 4 — Panel disclosure + rebuttal

Share all findings with all personas.
Each persona responds to findings from others:

- "UPHOLD: [finding ID] — [additional evidence]"
- "WITHDRAW: [finding ID] — [why the rebuttal was convincing]"
- "CHALLENGE: [finding ID] — [counter-argument with evidence]"

One round. No further debate.

## Step 4.5 — Validate agent JSON

Before synthesis, validate every agent's output. A malformed output is excluded from synthesis
and flagged as `[AGENT] output malformed — excluded`.

**Standard finding agents** (all except agent-evaluator): output must be a JSON array. Each
element must satisfy:
- `severity` is one of `BLOCKING`, `SIGNIFICANT`, `MINOR` (exact case)
- `finding` or `challenge` is a non-empty string
- `evidence` is a non-empty string that names a file, line, ADR, or specific reference — not a
  placeholder or empty string
- `recommendation` is a non-empty string

Any finding missing a required field, or with `evidence` as a placeholder (`"..."`, `"N/A"`,
`"<...>"`) is silently dropped. A persona whose entire output fails validation is excluded and noted.

**agent-evaluator**: outputs a single JSON object, not an array. Validate that it has `verdict`
(one of `APPROVE`, `EXTEND`, `REJECT`), `decision_rationale` (non-empty), and `gap_confirmed`
(non-empty or null). Treat REJECT as BLOCKING, EXTEND as SIGNIFICANT, APPROVE as MINOR for
synthesis severity mapping.

## Step 5 — Synthesis

Synthesis agent receives:

- Original output being reviewed
- All findings from all personas
- All rebuttals and challenges

Synthesis rules:

- Specific finding + evidence + not successfully rebutted = upheld
- Vague finding without evidence = MINOR at most, regardless of persona
- Successfully rebutted finding = downgrade one severity level or drop
- Multiple personas finding the same issue = increase severity

Produces a structured verdict (see docs/review-panels.md for the finding format and verdicts).

## Step 6 — Output verdict

```text
╔══════════════════════════════════════════════════════╗
║  ADVERSARIAL REVIEW — {task_type}                   ║
║  Panel: {persona list}                              ║
║  Verdict: {PASS | CONDITIONAL | FAIL}               ║
╚══════════════════════════════════════════════════════╝

BLOCKING FINDINGS ({N}):
  [{persona}] [{category}] {finding}
  Evidence: {specific reference}
  Status: UPHELD / WITHDRAWN

SIGNIFICANT FINDINGS ({N}):
  ...

MINOR FINDINGS ({N}):
  ...

SYNTHESIS:
  {reasoning for verdict}

NEXT ACTION:
  PASS        → proceed
  CONDITIONAL → fix before phase complete, can proceed now
  FAIL        → fix blocking findings, re-review before proceeding
```

## Step 6.5 — Persist to disk

**Blast radius: low** (writes within `.work/reviews/`). No human approval required.

```bash
DATE=$(date +%Y-%m-%d)
TASK_SLUG=$(echo "$TASK_TYPE" | tr '[:upper:]' '[:lower:]' | tr ' /' '-')
RUN_DIR=".work/reviews/adversarial-review-${DATE}-${TASK_SLUG}"
mkdir -p "$RUN_DIR"
```

For each persona that produced valid output, write `{RUN_DIR}/{persona-name}.md` using the
same individual agent file format as `/repo-health` Step 6a (findings table + recommendations).

Write the synthesised verdict to `{RUN_DIR}/report.md`. Convert the ASCII-box verdict from
Step 6 to markdown (use headings instead of box borders), preserving all findings, synthesis
reasoning, and next action. Each finding line should link to the persona's own file:
`[{persona}]({persona-name}.md)`.

---

## Step 7 — Feed into validation loop

If FAIL:

- Findings feed into refine prompt (only blocking findings)
- Do not include MINOR findings in refine prompt (noise)
- Max 2 adversarial review cycles before escalating to human

If verdict is FAIL after 2 cycles:

- Surface as blocked work item
- Include full review history
- Human must review before proceeding

## Frequency rules

Run /adversarial-review when invoked, or in any of these situations:

- Before /phase-complete on the work being closed
- Before any high blast radius action
- Every ~10 completed work items as a periodic system health check
- When any task required >2 validation loop refinements
- Whenever something feels off, or /change-direction is triggered

## Token efficiency

Panel members run in parallel — not sequential.
Budget: (3-5 personas × 1 call) + 1 synthesis call per review.
Each panel member uses its assigned model (see docs/review-panels.md — 17 personas on Haiku, 7 on Sonnet).
Synthesis agent uses Sonnet.
Do not include raw file contents in prompts — use compressed context.
