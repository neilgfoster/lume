# build-lume - snapshot

Updated: 2026-06-09 (iteration 003 handback)

## Done
- Discovery docs written (vision / scope / constraints / questions).
- File layout agreed: separated files + iterations/ dir, frontmatter carries phase.
- Iteration 001 ("Runnable orientation") merged (PR #2): `lume status`.
- Iteration 002 ("Engine as a tested module") merged (PR #3): Python package under .lume/engine/, OO + injected clock/root, state at .lume/workstreams/.

## Now
- Iteration 003 ("Gate-transition commands") accepted and on a PR, phase: accepted. Verbs approve/start/handback/accept/reject/redo flip phase via a single transition table; reject requires + records a reason, accept stamps a bare ACCEPTED line (no reason). 25 tests green. The whole loop - open, reject, redo, handback, accept - ran via its own verbs with no hand-edited frontmatter.

## Next
- A handback/snapshot recorder so the Done/Now/Next prose updates are assisted too (phase flips are now automated; snapshot prose is still hand-authored).
- Then the steps 1-5 loop is fully tooled; revisit which manual steps remain.
- Layout note: engine code at .lume/engine/, workstream state at .lume/workstreams/<slug>/.
