# Adopters

Who uses lume. This list is deliberately honest: the only adopters today are
lume itself and tredl — both authored by the same person, so there are still
zero *external* users. That is the evidence behind the "zero external users"
caveat in the [README](README.md); as genuinely independent rows appear, that
caveat weakens on evidence, not assertion.

The source of truth is [`ADOPTERS.json`](ADOPTERS.json). The table below is
**generated** from it by `tools/render_adopters.py` — to add yourself, edit
`ADOPTERS.json` (open a PR) and run the renderer; do not hand-edit the table.
lume's cross-repo scan reads `ADOPTERS.json` directly, so the data stays
deterministic and the markdown is just the human view.

<!-- BEGIN generated adopters table (source: ADOPTERS.json; run tools/render_adopters.py) -->
| Project | Adopter | Link | Since |
| --- | --- | --- | --- |
| lume | Neil Foster | https://github.com/neilgfoster/lume | 2026-06 |
| tredl | Neil Foster | https://github.com/neilgfoster/tredl | 2026-06 |
<!-- END generated adopters table -->

tredl is lume's first autonomous-operator consumer — the layer that drives the
iteration gates with Claude Code as the operator — and the source of the
discovery-driven backlog that shapes lume's roadmap (see workstream 0011).

Note: the cross-repo discovery scan (backlog item L1 — lume reading adopters'
`.lume/gaps/*.json` and ingesting them into its own backlog) is being built in
workstream 0011 (P2). These rows are forward-preparation for that mechanism: the
honest record of the intended adopters, not a claim that the full scan ships
today.
