# Working in the lume repo

This repo is built with lume, and it holds itself to lume's own discipline.

## The rule: every change goes through a lume workstream

Every change you (the agent) land in this repo must go through a lume
workstream. No commits outside an active workstream that is actively working.
This is a property of THIS repo, enforced for the agent. It is **not** a lume
feature and does not ship to lume's users (nothing for it lives under
`plugin/`).

## How to satisfy it

1. `lume status` - orient. If no workstream fits the change, open one:
   `lume new <slug> "<title>"`, then edit its `objective.json`.
2. `lume open "<title>" [-t discovery|planning|execution|closeout]` - open an
   iteration. Draft a crisp, checkable DoD in its content artifact.
3. `lume approve` -> `lume start` - move the iteration to the `working` phase.
4. Do the work, then `git commit` it. Write an honest self-review + handback,
   `lume handback`, and present it for the **operator's** accept/reject decision.
   On the operator's explicit instruction the agent may run `lume accept` /
   `lume reject` to execute that decision (see "Gates are the operator's"); it
   must never decide the gate itself.

Driving the loop and editing anything under `.lume/` need no commit, so you can
always create and start a workstream before the gate applies - it never
deadlocks.

## How it is enforced

`.claude/settings.json` wires a `PreToolUse` hook,
`.claude/hooks/require-workstream-commit.py`, that **denies `git commit`** unless
an active workstream has a current iteration in the `working` phase. It is a
**commit-only chokepoint**: you may read, explore, and edit freely, but nothing
**lands** in history outside a workstream.

- It gates the agent's tool calls, not the operator's own editor/terminal edits
  (the hook never sees those) - hence it constrains the agent more than the
  operator.
- It is a chokepoint, not a sandbox: raw file writes are not blocked, but they
  cannot be committed without a working iteration. Honour the rule; do not route
  around it.
- It activates at session start, so a freshly added/edited hook takes effect in
  the next session.

## Gates are the operator's

Per lume's defining rule, the **accept**/reject and **PR merge** gates belong to
the human operator. The gate exists to stop the **agent proceeding past the
operator's decision on its own** - not to make the operator context-switch to a
terminal. So the rule is about *who decides*, not *who types*:

- The agent **may** run `lume approve`, `lume accept`, and `lume reject` **only
  when the operator has explicitly instructed it for the current iteration in
  the conversation** (e.g. the operator replies "approve" / "accept" / "reject
  because X"). The agent must be able to point to that instruction. Running the
  verb then is *executing* the operator's decision, not making it.
- The agent **must never** run these verbs autonomously, speculatively, on
  inferred or assumed approval, because a previous turn said "proceed", or
  because the agent judges the work good. Operator silence, an earlier
  "proceed", and the agent's own confidence are all **insufficient** - each gate
  needs its own explicit instruction. When in doubt, stop and ask; never
  self-accept.
- The agent never merges a PR or bypasses branch protection - that gate stays
  strictly human regardless of any instruction.

## Other conventions

- No engine changes in discovery/planning iterations; record decisions with
  `lume decide` and build the plan with `lume plan`.
- Keep changes behaviour-preserving and run the tests (`python -m pytest -q`)
  before handback.
- All lume state is JSON validated against schemas (`lume schema <entity>`).
