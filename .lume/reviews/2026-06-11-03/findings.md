# Review findings - 2026-06-11-03

Provenance: lume review | 2026-06-11 | automated self-review, not external validation

## Direction decisions

### STANDING (unadopted from review 2026-06-11-01). Ecosystem-fit lens re-run live June 2026 (claude-plugins-official: 101 plugins, 33 Anthropic-built incl. code-review/feature-dev/security-guidance; community marketplace with automated safety screening). Native Tasks/sessions/auto-memory still cover generic cross-session persistence; no native feature or first-party plugin enforces operator accept/reject gates as deterministic state transitions over repo-resident, schema-validated, version-controlled audit state.

**Decision:** RE-AFFIRMED, still applies. lume's defensible wedge is (1) enforced operator gates as a deterministic state machine and (2) repo-resident, diffable, schema-validated audit state - not generic cross-session persistence. Reposition the README/vision one-liner around that wedge and flag the session-persistence framing as superseded-by-native. No operator verdict has been recorded since review-01; it is neither adopted nor declined.

**Rationale:** The live re-fetch confirms the wedge survives (a) native features and (b) first-party plugins. The charter's stay-true-to-intent / deprecation rule still mandates flagging the superseded persistence framing. Standing item carried forward per the prior-review follow-up instruction, not re-derived as new.

### STANDING (unadopted from review 2026-06-11-01). Plugins may bundle agents/ directories and .mcp.json servers; lume could ship a review subagent or state-introspection MCP server. Best-practice conformance re-checked live: no breaking divergences in lume's plugin structure.

**Decision:** RE-AFFIRMED, still holds. Do NOT build agents/ or MCP surface speculatively; they enter the backlog only on a gap record demonstrating demand. Record the conformance result (aligned, no divergences) again as this review's audit outcome.

**Rationale:** Consistent with the grow-by-demonstrated-need rule and ceremony-buys-its-cost. This is a 'keep declining' stance; confirming it each review prevents speculative scope creep.

## Proposed workstreams

### evidence-freshness: Fix stale evidence-tagged claims and guard derivable facts against drift

Serves goal: STANDING (unadopted from review 2026-06-11-01), now WORSENED. Honesty policy: every claim evidenced or flagged - stale [E] claims silently break lume's own adversarial-README rule.

No hand-authored count in README/docs disagrees with repo reality, and a CI guard covers the mechanically-derivable ones so [E] claims cannot silently rot again.

- (chore, committed) Sweep README.md, docs/*.md, ADOPTERS.md for stale facts and correct against current reality: test count, closed-workstream count, in-progress claim, adopter count.
  - evidence: Drift has grown since review-01: README.md:47,156 claim '313 passing tests' but pytest now reports 427 passed (was 401 at review-01). README.md:54-55 and docs/questions.md:41, docs/constraints.md:4-5, docs/vision.md:53-54 all say 'eight closed workstreams ... a ninth in progress' but .lume/workstreams/ holds 22, all closed.
- (chore, committed) Resolve the adopter-count contradiction: README.md:18 ('zero external adopters') and README.md:120 ('currently: just lume') now disagree with ADOPTERS.json (lume + tredl) and README.md:70 ('exercised in the tredl adopter repo'). Decide whether tredl (operator's own project) counts as external, then make all three surfaces consistent.
  - evidence: ADOPTERS.json lists 2 rows (lume, tredl); README.md:18/:120 still assert zero/just-lume; README.md:70 references the tredl adopter repo. Internal inconsistency introduced after the prior review added tredl.
- (slice, committed) Add a freshness guard for derivable claims: a CI-wired check asserting README's stated test count and workstream/adopter counts match derived reality, mirroring the existing version-consistency and render_adopters --check guards.
  - evidence: Precedent exists: pyproject==plugin.json version CI guard and generated ADOPTERS.md table - the drift class was engineered away elsewhere but not for prose counts, which is why the counts drifted twice across two reviews.

### value-signal: Start capturing the value signal: reject-rate and gate data from lume's own state

Serves goal: STANDING (unadopted from review 2026-06-11-01). questions.md assumptions 1 and 4 - the two biggest open claims (honest self-review; ceremony pays for itself) remain unmeasured and no workstream anywhere schedules measuring them.

A derived report of verdict statistics across all 22 workstreams exists, and a decision records what further measurement is or is not worth building.

- (spike, optional) Spike: derive verdict/reject-rate statistics from existing .lume/workstreams/*/state.json (per-workstream and overall: iterations, rejects, reject reasons, redo cycles); write up what the data does and does not say about assumptions 1 and 4.
  - evidence: docs/questions.md Reconciliation items 1 and 4 ('not tracked as data', 'UNMEASURED - the headline open question'); all verdicts already persisted in state.json across 22 workstreams - no new instrumentation needed for the first cut. The 0008 autonomy chain names 'falsifiable value/cost measurement' as a precondition, still unscheduled.

## Review gaps (META lens - gaps in this review itself)

### The emitted protocol embeds the full charter context verbatim (this run: ~1294 lines / 188KB, all 22 workstreams' objectives + decisions + plans + retros). It grows unbounded with every closed workstream, so review cost and the reviewer's ability to attend to all of it degrade monotonically as the project matures - the opposite of what a maturing project's review needs.

Why missed: The charter-gathering step was designed when the corpus was small (the first reviews seeded from ~15 workstreams) and optimised for completeness, not for scaling; no lens or emit option bounds or summarises the embedded context.

Proposed change: Add a relevance/recency bound or a summarisation pass to charter emission (e.g. full text for the last N workstreams + open items, one-line digests for older closed ones), or an emit flag to scope the embedded corpus, so review context stays bounded as the workstream count grows.

