# Adopters

Who uses lume. This list is deliberately honest: the only adopters today are
lume itself and tredl — both authored by the same person, so there are still
zero *external* users. That is the evidence behind the "zero external users"
caveat in the [README](README.md); as genuinely independent rows appear, that
caveat weakens on evidence, not assertion.

If you use lume in your own project, please add yourself: open a pull request
adding a row to the table below. Keep the format (it is meant to stay
machine-readable so lume can later read this file to find adopters and learn how
it's used).

| Project | Adopter | Link | Since |
| --- | --- | --- | --- |
| lume | Neil Foster | https://github.com/neilgfoster/lume | 2026-06 |
| tredl | Neil Foster | https://github.com/neilgfoster/tredl | 2026-06 |

tredl is lume's first autonomous-operator consumer — the layer that drives the
iteration gates with Claude Code as the operator — and the source of the
discovery-driven backlog that shapes lume's roadmap (see workstream 0011).

Note: the cross-repo discovery scan (backlog item L1 — lume reading adopters'
`discoveries/*.json` and ingesting them into its own backlog) is **not yet
implemented**. This row is forward-preparation for that mechanism: it is the
honest record of the intended adopter, not evidence that the scan works today.

<!--
Format note: one row per project. Columns are fixed (Project | Adopter | Link |
Since). "Since" is YYYY-MM. Add new rows below the header; do not reorder
columns. A future lume verb may parse this table — keep it valid.
-->
