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
   `lume handback`, and let the **operator** accept (`lume accept`) or reject.

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

Per lume's defining rule, the **accept** and **PR merge** gates belong to the
human operator. Drive the loop up to handback; never accept on the operator's
behalf, and never merge a PR or bypass branch protection.

## Other conventions

- No engine changes in discovery/planning iterations; record decisions with
  `lume decide` and build the plan with `lume plan`.
- Keep changes behaviour-preserving and run the tests (`python -m pytest -q`)
  before handback.
- All lume state is JSON validated against schemas (`lume schema <entity>`).
