# build-lume - decisions

Append-only. Newest at the bottom.

- 2026-06-09 | State split into separate files (objective/snapshot/decisions) + an iterations/ dir, one file per iteration | Cleanest review diffs and audit trail; orientation surface (snapshot) stays small and glanceable.
- 2026-06-09 | State carried in YAML-style frontmatter of the markdown files, no separate state.json | One source of truth, no drift; still deterministic to parse, so honors deterministic-over-inference without a second store.
- 2026-06-09 | Deterministic command layer written in Python 3 (stdlib only) | Readable frontmatter parsing that scales to phase transitions and gates later; no pip install; no LLM in the control path.
- 2026-06-09 | Retro 006: KEEP all 5 loop steps; none cut | Operator verdict net-positive; every step earns its keep (see retro.md). The one real cost (manual snapshot upkeep) was already engineered away in 004-005.
- 2026-06-09 | Retro 006: CHANGE - DoDs must be checked for completeness, not just crispness | Both rejects (002, 003) were requirements the DoD never encoded, not self-review dishonesty. When proposing a DoD, also ask "what could get this rejected that the DoD doesn't capture?"
- 2026-06-09 | Retro 006: re-orientation across a real multi-day gap is UNPROVEN; contract seams review+practice are UNPROVEN | All iterations were same-day; only the persistence seam was built. Not blockers; flagged for future validation. The next workstream exercises the practice seam.
- 2026-06-09 | build-lume CLOSED - objective met | Steps 1-5 are deterministic tooling and ran build-lume through 005 (incl. a full reject->redo->accept on its own verbs). See retro.md.
- 2026-06-09 | Next workstream = refine workstream process into an explicit lifecycle (discovery -> planning -> execution -> close-out), exercising the practice contract | Formalises what build-lume did ad hoc; pulls on the unproven practice seam; first gap: `lume open` hardcodes type=build.
