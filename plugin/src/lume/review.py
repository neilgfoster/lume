"""lume review - deterministic adversarial self-review plumbing (emit + ingest).

lume contains no LLM: the emit half GATHERS charter context from the repo and
EMITS a review protocol as text; the ingest half (bottom of this module) turns a
validated review result into lume artifacts. The reviewing agent does all judgement, then
hands a structured result back to `lume review ingest`. Determinism boundary:
same repo state + same discovered files in -> byte-identical protocol out. The
emit side reads the clock nowhere and writes nothing; the clock enters only at
ingest (the dated review folder).

Charter discovery is generic so the verb works in ANY lume repo:
- PRIMARY: lume state itself (every workstream's objective, decisions, plan,
  retro) - the one source guaranteed to exist, stating intent in lume's terms.
- SECONDARY: a capped, sorted pattern scan for charter-like docs.
- OVERRIDE: explicit --charter globs replace the scan entirely.
- DEGRADE: with thin/no docs the protocol still emits from lume state alone and
  tells the agent so explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path

from .validate import load_schema

# Doc-scan caps (decision, workstream 0015): bound protocol size, visibly.
MAX_DOC_FILES = 12
MAX_DOC_CHARS = 8192
_TRUNCATION_MARKER = "\n[... truncated by lume review at {} characters ...]"

# Charter-like docs are found by PATTERN, not fixed path - adopter repos keep
# intent in different places. This is a shape heuristic, not a doc list.
_DOC_PATTERNS = (
    "README*",
    "docs/**/*.md",
    "*.seed.md",
    "ADOPTERS*",
    "CONTRIBUTING*",
    "**/SKILL.md",
    ".claude/**/*.md",
)
_EXCLUDED_PARTS = {".git", ".lume", "node_modules", "__pycache__", ".venv"}
THIN_COVERAGE_THRESHOLD = 2

# The seven lenses. Names + instructions are the protocol contract; the
# ecosystem-fit lens deliberately instructs a LIVE lookup and embeds no
# feature/plugin/best-practice list (that would go stale and break determinism).
LENSES: tuple[tuple[str, str], ...] = (
    ("goal-fidelity / drift",
     "Compare what the project IS (code, verbs, docs) against what the charter "
     "says it is FOR. Name every place the implementation has drifted from the "
     "stated intent, and every charter promise with no implementation behind it."),
    ("honesty",
     "Hunt for claims the repo makes about itself that the evidence does not "
     "support: overstated README capabilities, 'done' items that are not done, "
     "caveats that exist in one doc but are dropped in another, tests that "
     "assert less than their names claim."),
    ("ecosystem fit",
     "Check redundancy, overlap, AND best-practice conformance against the "
     "CURRENT Claude Code ecosystem at review time - look it up now (web, "
     "official docs, the plugin marketplace); do not rely on a remembered or "
     "baked-in list, because the ecosystem changes. (a) Native features "
     "(skills, subagents, plan mode, todo tracking, hooks, memory, workflows): "
     "does the project duplicate any? (b) Official first-party plugins: does "
     "one already do this, or is one likely to absorb it? Apply the project's "
     "own deprecation rule honestly. (c) Official Claude Code / Anthropic best "
     "practices and conventions for plugin structure, skills, slash commands, "
     "agent/tool design, hooks, MCP, settings: where does the project diverge, "
     "and is each divergence a justified deliberate choice or unflagged drift? "
     "Conclude with the irreducible wedge that survives (a) and (b), and the "
     "best-practice gaps from (c)."),
    ("value / viability",
     "Per the charter's own cost rule: which parts visibly buy back more than "
     "they cost, which are ceremony, and which would not be missed if deleted? "
     "Judge against the project's stated constraints, not generic taste."),
    ("keystone / dependency risk",
     "Find the load-bearing pieces: single points of failure, assumptions "
     "everything rests on, dependencies (tools, platforms, conventions) whose "
     "change would invalidate core behavior. Grade how exposed each is."),
    ("vision coherence",
     "Read the charter sources as one document: do they still agree with each "
     "other and with the current state? Name contradictions between vision, "
     "constraints, docs, and recorded decisions, including stale 'current "
     "state' claims."),
    ("META / self-improvement",
     "Turn the review on itself. What might THIS review have missed: lenses "
     "that should exist but do not, evidence this protocol never told you to "
     "gather, blind spots, weak or trivially-satisfiable prompts, charter "
     "sources not consulted, finding types with no home in the Result "
     "contract? Record each as a review_gap (a self-improvement gap in the "
     "REVIEW ITSELF - not a project finding). If the review was genuinely "
     "thorough, say so explicitly rather than inventing gaps."),
)


def discover_docs(root: Path, charter_globs: list[str] | None) -> tuple[list[Path], int, str]:
    """Charter-doc paths under `root`, the count dropped by the cap, and the kind.

    With `charter_globs` (the --charter override) only those globs are used and
    the kind is 'override'; otherwise the built-in patterns scan ('discovered-doc').
    Paths are relative, sorted, deduped; the cap keeps the first MAX_DOC_FILES.
    """
    patterns = charter_globs if charter_globs else list(_DOC_PATTERNS)
    kind = "override" if charter_globs else "discovered-doc"
    found: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _EXCLUDED_PARTS.intersection(rel.parts):
                continue
            found.add(rel)
    ordered = sorted(found, key=lambda p: p.as_posix())
    dropped = max(0, len(ordered) - MAX_DOC_FILES)
    return ordered[:MAX_DOC_FILES], dropped, kind


def _read_capped(root: Path, rel: Path) -> tuple[str, bool]:
    """File content capped at MAX_DOC_CHARS, plus whether it was truncated."""
    text = (root / rel).read_text(errors="replace")
    if len(text) <= MAX_DOC_CHARS:
        return text, False
    return text[:MAX_DOC_CHARS] + _TRUNCATION_MARKER.format(MAX_DOC_CHARS), True


def gather_charter(repo, charter_globs: list[str] | None) -> dict:
    """Everything the protocol is seeded from, gathered deterministically.

    Returns {workstreams, docs, doc_kind, dropped_docs}: workstreams carry each
    workstream's objective, decisions, plan, and retro verdict (the PRIMARY
    charter source); docs carry the capped SECONDARY/OVERRIDE file excerpts.
    """
    root = repo.project_root()
    lume_dir = root / ".lume"
    workstreams = []
    for ws in repo.workstreams(lume_dir):
        objective = ws.objective_doc()
        decisions = ws.decisions_doc() or {"entries": []}
        retro = ws.retro_doc()
        plan = ws.plan_items() or []
        workstreams.append({
            "id": ws.id,
            "slug": ws.name,
            "status": ws.status,
            "title": objective.get("title", ""),
            "objective": objective.get("text", ""),
            "decisions": decisions["entries"],
            "plan": [{"id": p.id, "type": p.type, "tag": p.tag, "iter": p.iter,
                      "sketch": p.sketch} for p in plan],
            "retro_verdict": (retro or {}).get("overall_verdict"),
        })
    doc_paths, dropped, kind = discover_docs(root, charter_globs)
    docs = []
    for rel in doc_paths:
        content, truncated = _read_capped(root, rel)
        docs.append({"path": rel.as_posix(), "content": content,
                     "truncated": truncated})
    return {"workstreams": workstreams, "docs": docs, "doc_kind": kind,
            "dropped_docs": dropped}


def charter_sources(charter: dict) -> list[dict]:
    """The labelled source list for --json: which inputs seeded the protocol."""
    sources = [{"source": f"workstream {w['id']} ({w['slug']})", "kind": "lume-state"}
               for w in charter["workstreams"]]
    sources += [{"source": d["path"], "kind": charter["doc_kind"]}
                for d in charter["docs"]]
    return sources


def result_contract_skeleton() -> dict:
    """The shape `ingest` consumes, embedded in the protocol for the agent."""
    return {
        "direction_decisions": [
            {"context": "...", "decision": "...", "rationale": "..."}],
        "proposed_workstreams": [
            {"slug": "...", "title": "...", "serves_goal": "...",
             "objective": "...", "critical_path": False,
             "plan_items": [
                 {"sketch": "...", "type": "epic|slice|spike|chore",
                  "tag": "committed|optional", "evidence": "..."}]}],
        "review_gaps": [
            {"gap": "...", "why_missed": "...", "proposed_change": "..."}],
        "provenance": {
            "source": "lume review", "date": "YYYY-MM-DD",
            "note": "automated self-review, not external validation"},
    }


def _workstream_block(w: dict) -> list[str]:
    lines = [f"### workstream {w['id']} {w['slug']} ({w['status']}): {w['title']}",
             "", w["objective"] or "(no objective text)", ""]
    if w["decisions"]:
        lines.append("Decisions:")
        lines += [f"- {e['date']} [{e['context']}] {e['decision']} - {e['rationale']}"
                  for e in w["decisions"]]
        lines.append("")
    if w["plan"]:
        lines.append("Plan:")
        lines += [f"- {p['id']} ({p['type']}, {p['tag']}"
                  f"{', iter ' + format(p['iter'], '03d') if p['iter'] else ''}): "
                  f"{p['sketch']}" for p in w["plan"]]
        lines.append("")
    if w["retro_verdict"]:
        lines += [f"Retro verdict: {w['retro_verdict']}", ""]
    return lines


def build_protocol(charter: dict) -> str:
    """The full protocol text. Pure function of the gathered charter."""
    out: list[str] = [
        "# Adversarial self-review protocol (lume review)",
        "",
        "You are the reviewing agent. lume gathered the context below "
        "deterministically; all judgement is yours. Review the PROJECT against "
        "its charter through every lens, then review THIS REVIEW against itself "
        "(the META lens). Steelman each finding before grading it. Dedupe "
        "against the current plan and decisions embedded below - do not "
        "re-propose work that is already planned or decided.",
        "",
        "## Charter context - from lume state (primary source)",
        "",
    ]
    for w in charter["workstreams"]:
        out += _workstream_block(w)
    n = len(charter["docs"])
    label = {"override": "operator --charter override",
             "discovered-doc": "pattern scan"}[charter["doc_kind"]]
    out += [f"## Charter context - docs ({label}: {n} file(s) found)", ""]
    if charter["dropped_docs"]:
        out += [f"NOTE: {charter['dropped_docs']} additional file(s) matched but "
                f"were dropped by the {MAX_DOC_FILES}-file cap - consult them "
                "directly if a lens needs more.", ""]
    for d in charter["docs"]:
        out += [f"### {d['path']}", "", d["content"], ""]
    if n < THIN_COVERAGE_THRESHOLD:
        out += [
            f"WARNING: charter doc coverage is thin: {n} file(s) found. Derive "
            "the project's goals primarily from the lume objectives, decisions, "
            "and plans above, and flag the missing charter documentation as "
            "itself a finding.",
            "",
        ]
    out += ["## Lenses", ""]
    for i, (name, instruction) in enumerate(LENSES, 1):
        out += [f"{i}. {name}", f"   {instruction}", ""]
    out += [
        "## Method",
        "",
        "For each finding: name the lens, grade severity (low|medium|high), "
        "give a verdict, and cite concrete evidence (file, doc, decision, or "
        "ecosystem source consulted). Steelman the project's position first; "
        "only findings that survive the steelman go in the result.",
        "",
        "## Result contract",
        "",
        "Produce ONE JSON file in exactly this shape (schema: "
        "`lume schema review_result`), then run `lume review ingest <path>`:",
        "",
        "```json",
        json.dumps(result_contract_skeleton(), indent=2),
        "```",
        "",
        "Mapping on ingest (emitted as commands for the operator, never "
        "executed by lume): proposed_workstreams -> lume new + lume plan add; "
        "direction_decisions -> lume decide; review_gaps -> lume gap add. "
        "provenance.note must state this is an automated self-review, not "
        "external validation.",
    ]
    return "\n".join(out)


def emit_json(charter: dict, protocol: str) -> dict:
    """The --json result object for `lume review emit`."""
    return {
        "result": "review_emit",
        "charter_sources": charter_sources(charter),
        "plan": [p for w in charter["workstreams"] for p in w["plan"]],
        "decisions": [e for w in charter["workstreams"] for e in w["decisions"]],
        "lenses": [name for name, _ in LENSES],
        "result_schema": load_schema("review_result"),
        "protocol": protocol,
    }


# ---------------------------------------------------------------------------
# Ingest half: deterministic conversion of a validated review result into
# lume artifacts. The clock enters here (folder date); emit never reads it.

_PLAN_TYPE_MAP = {"spike": "discovery", "epic": "planning",
                  "slice": "execution", "chore": "execution"}


def next_review_slug(lume_dir: Path, today: str) -> str:
    """The dated review folder name: review-<today>-NN, NN the first free
    zero-padded daily sequence (01, 02, ...) given the folders already present.
    Deterministic in (existing folders, clock date); never reuses a taken NN."""
    existing = {p.name for p in Path(lume_dir).glob(f"review-{today}-*")
                if p.is_dir()}
    n = 1
    while f"review-{today}-{n:02d}" in existing:
        n += 1
    return f"review-{today}-{n:02d}"


def build_findings_md(result: dict, review_slug: str) -> str:
    """The human-readable report - the primary captured record of the review."""
    p = result["provenance"]
    out = [
        f"# Review findings - {review_slug}",
        "",
        f"Provenance: {p['source']} | {p['date']} | {p['note']}",
        "",
        "## Direction decisions",
        "",
    ]
    if result["direction_decisions"]:
        for d in result["direction_decisions"]:
            out += [f"### {d['context']}", "",
                    f"**Decision:** {d['decision']}", "",
                    f"**Rationale:** {d['rationale']}", ""]
    else:
        out += ["(none)", ""]
    out += ["## Proposed workstreams", ""]
    if result["proposed_workstreams"]:
        for w in result["proposed_workstreams"]:
            out += [f"### {w['slug']}: {w['title']}"
                    f"{' [critical path]' if w['critical_path'] else ''}", "",
                    f"Serves goal: {w['serves_goal']}", "",
                    w["objective"], ""]
            for item in w["plan_items"]:
                out += [f"- ({item['type']}, {item['tag']}) {item['sketch']}",
                        f"  - evidence: {item['evidence']}"]
            out.append("")
    else:
        out += ["(none)", ""]
    out += ["## Review gaps (META lens - gaps in this review itself)", ""]
    if result["review_gaps"]:
        for g in result["review_gaps"]:
            out += [f"### {g['gap']}", "",
                    f"Why missed: {g['why_missed']}", "",
                    f"Proposed change: {g['proposed_change']}", ""]
    else:
        out += ["(none - the review judged itself thorough)", ""]
    return "\n".join(out)


def result_to_store_doc(result: dict, review_slug: str) -> dict:
    """The structured result in the discovery artifact shape ({title, sections})
    so it persists through the store seam against the existing schema."""
    return {
        "title": f"Review result - {review_slug}",
        "sections": [
            {"heading": "provenance", "body": json.dumps(result["provenance"], indent=2, sort_keys=True)},
            {"heading": "direction_decisions", "body": json.dumps(result["direction_decisions"], indent=2, sort_keys=True)},
            {"heading": "proposed_workstreams", "body": json.dumps(result["proposed_workstreams"], indent=2, sort_keys=True)},
            {"heading": "review_gaps", "body": json.dumps(result["review_gaps"], indent=2, sort_keys=True)},
        ],
    }


def queue_commands(result: dict, review_slug: str) -> list[str]:
    """The deterministic command plan that queues the results - emitted for the
    operator, NEVER executed by lume (the gates stay the operator's)."""
    commands: list[str] = []
    for w in result["proposed_workstreams"]:
        commands.append(f'lume new {w["slug"]} "{w["title"]}"')
        for item in w["plan_items"]:
            commands.append(
                f'lume plan add -w {w["slug"]} -t {_PLAN_TYPE_MAP[item["type"]]} '
                f'-g {item["tag"]} "{item["sketch"]}"')
    for d in result["direction_decisions"]:
        commands.append(f'lume decide -c "{d["context"]}" "{d["decision"]}" "{d["rationale"]}"')
    for g in result["review_gaps"]:
        commands.append(
            f'lume gap add "{g["gap"]}" -c "{review_slug}: missed because '
            f'{g["why_missed"]}; proposed: {g["proposed_change"]}"')
    return commands
