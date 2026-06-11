# Review findings - review-2026-06-11-01

Provenance: lume review | 2026-06-11 | automated self-review, not external validation

## Direction decisions

### Ecosystem-fit lens (live lookup, June 2026): Claude Code native Tasks (persisted in ~/.claude/tasks/ with dependency graphs, default since v2.1.142), sessions/resume, auto memory, and Agent View now cover most of 'persist iteration state across interrupted sessions' - a large part of lume's original positioning. No native feature or first-party marketplace plugin (closest: project-manager, advisory only) provides enforced operator accept/reject gates as state transitions, nor repo-resident, schema-validated, version-controlled audit state.

**Decision:** lume's defensible wedge is (1) enforced operator gates as a deterministic state machine and (2) repo-resident, diffable, schema-validated audit state - not generic cross-session persistence. Reposition the README/vision one-liner around that wedge, and per the charter's own deprecation rule, explicitly flag the session-persistence framing as superseded-by-native rather than continuing to lead with it.

**Rationale:** The charter's stay-true-to-intent non-negotiable mandates auditing against native features and deprecating superseded surface. Tasks supersedes the persistence story; the gate machine and in-repo auditable state are the irreducible remainder the ecosystem demonstrably lacks. Claiming the superseded part dilutes the honest README.

### Ecosystem lens also surfaced structural opportunities: plugins may now bundle agents/ directories and .mcp.json servers; lume could ship a review subagent or a state-introspection MCP server. Best-practice conformance check found no breaking divergences in lume's plugin structure (manifest, skills, frontmatter, hooks, marketplace source all aligned with current conventions).

**Decision:** Do NOT build the agents/ or MCP opportunities speculatively; they enter the backlog only if a gap record demonstrates demand, per the existing grow-by-demonstrated-need rule. Record the best-practice conformance result (aligned, no divergences) as the audit outcome.

**Rationale:** Consistent with the L5/template decision pattern (mechanism on demand, never speculative) and ceremony-buys-its-cost. The conformance result is worth recording so the next review can diff against it.

## Proposed workstreams

### evidence-freshness: Fix stale evidence-tagged claims and guard derivable facts against drift

Serves goal: Honesty policy: every claim evidenced or flagged - stale [E] claims silently break lume's own adversarial-README rule

The README's evidence-tagged claims have drifted: '313 passing tests' (actual: 401), 'eight closed workstreams, a ninth in progress' (actual: 15 closed, 1 active), 'ADOPTERS.md - currently: just lume' (actual: lume + tredl), and ADOPTERS.md still says the gap scan 'is being built in workstream 0011 (P2)' though it shipped. The same stale counts appear in docs/questions.md, docs/constraints.md's status banner, and docs/vision.md's reconciliation. Fix all of them, and where a fact is mechanically derivable (test count, workstream count, adopter count), either derive it or add a CI consistency check in the pattern already used for plugin.json/pyproject versions and the generated ADOPTERS table, so [E] claims cannot silently rot again. Done when no hand-authored count in README/docs disagrees with repo reality and a guard covers the derivable ones.

- (chore, committed) Sweep README.md, ADOPTERS.md, docs/*.md for stale facts (test count, workstream count, adopter count, 'being built' notes) and correct them against current reality
  - evidence: README.md:47,54,120,156; docs/vision.md:53; docs/constraints.md:4; docs/questions.md:41; ADOPTERS.md L1-note vs merged PR #23; pytest reports 401 passed vs claimed 313
- (slice, committed) Add a freshness guard for derivable claims: a small check (test-or-tools script, CI-wired) asserting the README's stated test count and workstream/adopter counts match derived reality, mirroring the existing version-consistency and render_adopters --check guards
  - evidence: Existing precedent: pyproject==plugin.json version CI guard (0011 P11) and generated ADOPTERS.md table (0011 P16) - the drift class was already engineered away elsewhere but not for prose counts

### value-signal: Start capturing the value signal: reject-rate and gate data from lume's own state

Serves goal: questions.md assumptions 1 and 4 - the two biggest open claims (honest self-review; ceremony pays for itself) are unmeasured and no measurement work is planned anywhere

lume's headline claim (ceremony buys back more time than it costs) and its second assumption (self-review is honest, measured by reject rate at the human gate) are both marked unmeasured in docs/questions.md, and no workstream or plan item anywhere proposes measuring them - the 0008 objective names 'falsifiable value/cost measurement' as a precondition on the autonomy chain but nothing schedules it. The cheap first step needs no new instrumentation: every verdict (accept/reject, with reasons) is already in schema-validated state across 16 workstreams. A spike that derives reject-rate and gate-traffic statistics from existing state would convert assumption 1 from anecdote to data and scope what (if anything) is worth instrumenting for assumption 4. Done when a derived report of verdict statistics across all workstreams exists and a decision records what further measurement is or is not worth building.

- (spike, optional) Spike: derive verdict/reject-rate statistics from existing .lume/workstreams/*/state.json (per-workstream and overall: iterations, rejects, reject reasons, redo cycles); write up what the data does and does not say about assumptions 1 and 4
  - evidence: docs/questions.md Reconciliation items 1 and 4 ('not tracked as data', 'UNMEASURED - the headline open question'); README Status & evidence table rows marked [U]; all verdicts already persisted in state.json

## Review gaps (META lens - gaps in this review itself)

### The protocol embeds charter docs verbatim but never instructs the reviewer to mechanically verify the repo's own evidence-tagged claims against current reality (run the test suite, count workstreams/adopters). The stale-313-tests finding was caught only because the reviewer ran pytest unprompted.

Why missed: The emit verb gathers text deterministically; the protocol's honesty lens asks for unsupported claims but assumes reading, not executing, is the verification method.

Proposed change: Add an explicit instruction to the honesty lens: re-derive every mechanically checkable [E]-tagged claim (test count, workstream/adopter counts, CI status) before grading, and treat any mismatch as a finding.

### No trust/security lens. DoD command checks execute author-supplied shell, the commit-gate hook runs as a PreToolUse script, and gap scan clones and reads arbitrary adopter repos - none of the seven lenses asks whether these trust boundaries are still appropriate as adoption grows.

Why missed: The lens set was derived from charter fidelity concerns (drift, honesty, value, ecosystem); trust was decided per-feature (e.g. the FORK 2 sandbox deferral) and never aggregated into a review dimension.

Proposed change: Add a trust-boundaries lens (or fold into keystone): enumerate every place lume executes or ingests external content (command checks, hooks, adopter scans) and re-grade each deferral against current adoption.

### The Result contract has no home for small direct fixes: a one-line stale-doc correction must be wrapped into a full proposed_workstream to be queued, which is heavier than the finding warrants and discourages recording small findings.

Why missed: The contract maps findings only to workstream/decision/gap, mirroring lume's existing verbs; no lighter-weight finding type was designed.

Proposed change: Either document the convention that small fixes are chore plan items proposed against an existing or housekeeping workstream, or extend review_result with a 'fixes' list that ingest maps to a single emitted chore-bundle workstream.

