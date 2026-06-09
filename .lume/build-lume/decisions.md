# build-lume - decisions

Append-only. Newest at the bottom.

- 2026-06-09 | State split into separate files (objective/snapshot/decisions) + an iterations/ dir, one file per iteration | Cleanest review diffs and audit trail; orientation surface (snapshot) stays small and glanceable.
- 2026-06-09 | State carried in YAML-style frontmatter of the markdown files, no separate state.json | One source of truth, no drift; still deterministic to parse, so honors deterministic-over-inference without a second store.
- 2026-06-09 | Deterministic command layer written in Python 3 (stdlib only) | Readable frontmatter parsing that scales to phase transitions and gates later; no pip install; no LLM in the control path.
