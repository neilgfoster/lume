---
name: lume
description: Drive the lume iteration loop - a deterministic, operator-gated workstream engine. Use when working in a repo that has a `.lume/` directory, or when the user asks to seed lume, start/continue a workstream, open an iteration, or move one through its gates (approve, start, handback, accept, reject). lume tracks goals as workstreams, work as gated iterations, and keeps all state as inspectable JSON.
---

# Driving lume

lume is a deterministic control layer for getting work done in gated iterations.
It does not use an LLM in any verb or gate - it reads, validates, and writes
on-disk JSON state. You (the agent) do the thinking and the work; lume keeps the
loop honest and the state inspectable. The defining rule: **the machine does not
act without the operator** - the accept/reject gate is always the human's.

The `lume` command is on your PATH (this plugin ships it). It is fully
self-describing - lean on that instead of guessing:

- `lume verbs` - list every verb with a one-line summary.
- `lume verbs <verb>` - usage, args, and flags for one verb.
- `lume --json <verb> ...` - machine-readable output (and errors) for any verb.
- `lume status` - re-orient: the current workstream, its objective, the live
  iteration's phase, and Done / Now / Next. Run `lume status` with no `-w` for
  the cross-workstream queue. **Always start here.**

## The phase machine

An iteration moves through fixed phases; each move is a specific verb (an
arbitrary phase can never be set):

```
proposed --approve--> approved --start--> working --handback--> handback
handback --accept--> accepted        (the workstream can then open the next iteration)
handback --reject--> rejected --redo--> working
```

A new iteration can only be opened once the latest one is `accepted`.

## The loop (playbook)

1. **Orient.** Run `lume status`. Read the phase and act from it - the next verb
   is determined by where the iteration sits, not by guesswork.
2. **Seed (new repo only).** If there is no `.lume/` yet, `lume seed` bootstraps
   it: `--new` for a fresh project (captures why/scope/constraints/done-when),
   `--existing` to map an existing repo. This is the operator's first step.
3. **Open the next iteration.** `lume open "<title>" [-t discovery|planning|execution|closeout]`.
   It is refused unless the latest iteration is accepted. Default type is
   execution; lead a new area with discovery then planning before execution.
4. **Draft a crisp DoD.** Edit the iteration's content artifact so the DoD items
   are binary and checkable (a reader can tell done from not-done). Then have the
   **operator approve** - do not self-approve substantive work.
5. **Do the work.** `lume start`, then carry out the iteration. When finished,
   check the DoD items, and write an honest **self-review** (what holds, what is
   weak, what was deferred - do not paper over gaps) and a **handback** summary.
   Then `lume handback`.
6. **Operator gate.** Present the handback and **let the human accept or reject**:
   `lume accept`, or `lume reject "<reason>"`. After a reject, `lume redo`
   resumes work to address the reason. Never accept on the operator's behalf.

## Conventions

- All artifacts are JSON, validated against schemas (`lume schema <entity>`,
  `lume entities`). Read and write them directly; lume validates on read.
- `-w <id-or-slug>` targets a workstream when more than one is active; otherwise
  the sole active one is used.
- Discovery and planning iterations produce findings/decisions and a plan - no
  engine/product code in those phases. Record decisions with `lume decide` and
  build the plan with `lume plan add` / `lume plan link`.
- Keep changes behaviour-preserving and run the project's tests before handback.
- A DoD item may carry a machine-checkable `check` (`command` exit-0,
  `file-exists`, or `schema-valid`) beside its prose. `lume accept` evaluates
  the current iteration's checks and **refuses** if any fail; `lume check`
  dry-runs them read-only (no transition). Prefer a `check` wherever a DoD item
  is mechanically verifiable, so the gate is a real test, not just an assertion;
  leave genuinely subjective items prose-only for the operator to judge. Command
  checks run author-supplied shell - trust them as you would the test suite.
- Cross-repo capability gaps live in `gaps/<source>-<id>.json` at a repo root.
  `lume gap add` records one; `lume gap scan` reads the repos in `ADOPTERS.json`
  (its table generates `ADOPTERS.md`), git-clones each into a worktree, and
  ingests their open gaps into lume's `gaps/` as `acknowledged` (idempotent on
  `(source, id)`, source taken from the ADOPTERS project name); `lume gap
  resolve <source> <id>` marks one resolved. v0.1 is ingest-only - no round-trip
  back to the adopter yet.

When in doubt about a verb's exact arguments, ask lume: `lume verbs <verb>`.
