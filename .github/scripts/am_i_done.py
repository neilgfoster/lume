#!/usr/bin/env python3
"""
am_i_done.py — deterministic completion gate.

Runs every applicable check locally and against CI. Exits 0 only when
all checks pass. Designed to be called by both humans and agents.

Usage:
  python3 .github/scripts/am_i_done.py                  # local checks only
  python3 .github/scripts/am_i_done.py --check git      # single check
  python3 .github/scripts/am_i_done.py --json           # machine-readable output
  python3 .github/scripts/am_i_done.py --pr 42          # + template, threads, dependabot
  python3 .github/scripts/am_i_done.py --pr 42 --check ci  # poll CI check status

Checks without --pr (mirrors CI jobs where possible — run these locally first):
  budget    - review panel budget tier and queue depth
  git       - working tree clean, not on main
  branch    - branch name follows naming convention (feat/, fix/, refactor/, docs/, chore/, spike/)
  config    - validate MANDATORY_AGENTS table is consistent with actual agent files on disk
  commands  - detect stale work-item IDs in .claude/commands/ (reads from configured backend)
  dispatch  - enforce mandatory agent floor for a review panel (requires --panel; not run by default)
  streams   - validate no file overlap across parallel worktree streams (requires --streams; not run by default)
  schemas   - validate markdown files against .work/config/markdown-schemas.json
  markdown  - pymarkdown lint (if pymarkdown available)
  lint      - ruff check (if ruff available)
  types     - mypy --strict (if mypy available and src/, lib/, or app/ exists)
  tests     - pytest (if tests/ exists)

Additional checks enabled by --pr N (require gh CLI + GitHub auth):
  template  - PR body matches .github/PULL_REQUEST_TEMPLATE.md
  threads   - no unresolved PR review threads (deterministic via GitHub GraphQL)
  dependabot - no open Dependabot security alerts (graceful skip if not configured)
  ci        - poll GitHub CI check status (requires --check ci --pr N; not run by default)

Note: CodeQL analysis (python, actions) runs in CI only and cannot be replicated locally.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Any, Optional

# budget_manager lives alongside this script. The integration is best-effort:
# if budget_manager.py is not present (its own PR has not landed yet) the
# `budget` check is a soft no-op.
_BUDGET_MGR = os.path.join(os.path.dirname(__file__), "budget_manager.py")
_SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__))
_GEN_METADATA = os.path.join(_SCRIPTS_DIR, "gen_skill_metadata.py")
# Navigate up from skill/hedl/scripts/ to the hedl repo root (3 levels)
_HEDL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPTS_DIR)))


def _hedl_version() -> str:
    try:
        pyproject = os.path.join(_HEDL_ROOT, "pyproject.toml")
        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)
        return str(data.get("project", {}).get("version", "unknown"))
    except Exception:
        return "unknown"

try:
    REPO_ROOT = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True,
        timeout=10,
    ).strip()
except FileNotFoundError:
    print("Error: git is not installed or not on PATH", file=sys.stderr)
    sys.exit(1)
except subprocess.TimeoutExpired:
    print("Error: git rev-parse timed out", file=sys.stderr)
    sys.exit(1)
except subprocess.CalledProcessError:
    print("Error: not inside a git repository", file=sys.stderr)
    sys.exit(1)


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    detail: str = ""


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }

    def print_human(self) -> None:
        width = 60
        print(f"\n{'─' * width}")
        print("  am_i_done?")
        print(f"{'─' * width}")
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            icon = "+" if r.passed else "x"
            print(f"  [{icon}] {r.name:<12} {status}  {r.message}")
            if r.detail and not r.passed:
                for line in r.detail.strip().splitlines()[:10]:
                    print(f"           {line}")
        print(f"{'─' * width}")
        if self.passed:
            print("  DONE — all checks pass.\n")
        else:
            failed_names = ", ".join(r.name for r in self.failed)
            print(f"  NOT DONE — failing: {failed_names}\n")
        print(f"{'─' * width}\n")


def run(cmd: list[str], cwd: str = REPO_ROOT, timeout: int = 120) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"timed out after {timeout}s: {' '.join(cmd)}"


def _load_hedl_config() -> Optional[dict[str, Any]]:
    """Load hedl.toml from REPO_ROOT. Returns None if absent or unreadable."""
    path = os.path.join(REPO_ROOT, "hedl.toml")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return None


def _get_gate_timeout(config: Optional[dict[str, Any]]) -> int:
    if config is None:
        return 120
    gate_section = config.get("gate") or {}
    return int(gate_section.get("timeout", 120))


# WORK-0021: a [verify] command may only invoke an allow-listed executable,
# named bare (no path), with no shell-control metacharacters. This is
# DEFENSE IN DEPTH, not a complete RCE control: hedl.toml is repo-committed and
# the gate runs on PR heads in CI, so a malicious PR could still achieve
# execution through an allowed runner that executes committed repo content
# (pytest loads conftest.py; make runs a committed Makefile; npm/pnpm run
# package.json scripts). What the allow-list DOES close is the trivial inline
# vector — a one-line `python -c '...'` / `bash -c '...'` / `node -e '...'`
# straight from hedl.toml. The real control for untrusted PRs is GitHub's
# "require approval to run workflows for outside/first-time contributors"
# (a CI setting), not this list. See skill/hedl/references/tiers.md.
_VERIFY_DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {"pytest", "mypy", "ruff", "npm", "pnpm", "make"}
)
# Never allowed, even if an operator lists them under [gate] allowed_commands:
# interpreters and execution forwarders turn a one-line [verify] entry into
# arbitrary inline code, defeating the allow-list. The set is necessarily
# non-exhaustive (it cannot enumerate every interpreter) — it blocks the obvious
# forwarders so the operator cannot trivially re-open the inline vector.
_VERIFY_DENYLIST: frozenset[str] = frozenset(
    {
        "env", "sh", "bash", "zsh", "dash", "fish", "busybox",
        "python", "python2", "python3", "node", "nodejs", "deno", "bun",
        "ruby", "perl", "php", "lua", "tclsh", "pwsh", "powershell",
        "xargs", "find", "awk", "eval", "exec",
    }
)
_SHELL_METACHARS = re.compile(r"[;&|<>$`\n\r\x00\t]")


def _verify_allowlist(config: Optional[dict[str, Any]]) -> frozenset[str]:
    """Effective [verify] executable allow-list: the built-in default plus any
    bare executable names operators add under hedl.toml [gate] allowed_commands.

    The extension is additive (it can never narrow the default and break the
    standard lint/types/test runners) and itself constrained: an entry is
    ignored unless it is a bare name (no path separator), free of shell
    metacharacters, and not in the interpreter/forwarder denylist — so the
    operator cannot re-open the inline-code vector through config.
    """
    allowed = set(_VERIFY_DEFAULT_ALLOWLIST)
    gate = (config or {}).get("gate") or {}
    extra = gate.get("allowed_commands", [])
    if isinstance(extra, list):
        for name in extra:
            if (
                isinstance(name, str)
                and name
                and "/" not in name
                and "\\" not in name
                and not _SHELL_METACHARS.search(name)
                and name not in _VERIFY_DENYLIST
            ):
                allowed.add(name)
    return frozenset(allowed)


def _run_declared_check(
    name: str, spec: Any, gate_timeout: int, allowed: frozenset[str]
) -> CheckResult:
    """Run a single check declared in hedl.toml [verify].

    spec is either a string (short form) or a dict with 'cmd' and optional
    'timeout'/'cwd' (long form). Commands are parsed with shlex.split and run
    via subprocess list form — no shell=True. The executable (cmd[0]) must be a
    bare name (no path) present in `allowed`; shell metacharacters are rejected;
    a long-form 'cwd' must stay within the repo. WORK-0021.
    """
    if isinstance(spec, str):
        cmd_str, timeout, cwd = spec, gate_timeout, REPO_ROOT
    elif isinstance(spec, dict):
        cmd_str = str(spec.get("cmd", ""))
        timeout = int(spec.get("timeout", gate_timeout))
        rel = str(spec.get("cwd", ""))
        if rel:
            cwd = os.path.realpath(os.path.join(REPO_ROOT, rel))
            root = os.path.realpath(REPO_ROOT)
            if cwd != root and not cwd.startswith(root + os.sep):
                return CheckResult(
                    name, False, f"[verify.{name}] cwd '{rel}' escapes the repo root"
                )
        else:
            cwd = REPO_ROOT
    else:
        return CheckResult(name, False, f"[verify.{name}] must be a string or table")

    if _SHELL_METACHARS.search(cmd_str):
        return CheckResult(
            name, False,
            f"[verify.{name}] contains shell metacharacters — not allowed "
            "(commands run with shell=False). Wrap pipelines in a script.",
        )

    try:
        cmd = shlex.split(cmd_str)
    except ValueError as exc:
        return CheckResult(name, False, f"[verify.{name}] command parse error: {exc}")

    if not cmd:
        return CheckResult(name, False, f"[verify.{name}] has no command")

    exe = cmd[0]
    if "/" in exe or "\\" in exe:
        return CheckResult(
            name, False,
            f"[verify.{name}] executable must be a bare name, not a path: '{exe}'. "
            "Put the tool on PATH and reference it by name.",
        )

    # Defense in depth: reject denied interpreters/forwarders here too, so the
    # denylist holds even if a future caller hands us an allow-list that was not
    # built through _verify_allowlist.
    if exe in _VERIFY_DENYLIST:
        return CheckResult(
            name, False,
            f"[verify.{name}] executable '{exe}' is a denied interpreter/forwarder.",
        )

    if exe not in allowed:
        return CheckResult(
            name, False,
            f"[verify.{name}] executable '{exe}' not in allow-list "
            f"({', '.join(sorted(allowed))}). Add its name to hedl.toml "
            "[gate] allowed_commands if intended.",
        )

    if not shutil.which(exe):
        return CheckResult(name, False, f"{exe} not found (declared in hedl.toml [verify.{name}])")

    code, out, err = run(cmd, cwd=cwd, timeout=timeout)
    if code != 0:
        combined = (out + err).strip()
        lines = combined.splitlines()[-30:]
        return CheckResult(name, False, f"{cmd[0]} failed", "\n".join(lines))
    return CheckResult(name, True, f"{cmd[0]} passed")


def check_git() -> CheckResult:
    _, out, _ = run(["git", "status", "--porcelain"])
    if out.strip():
        return CheckResult(
            "git",
            False,
            "uncommitted changes",
            out.strip(),
        )

    _, branch, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch.strip()
    if not branch:
        return CheckResult("git", False, "could not determine current branch")
    if branch == "main":
        return CheckResult(
            "git",
            False,
            "on main branch — create a feature branch first",
        )

    return CheckResult("git", True, f"clean, on {branch}")


BRANCH_PATTERN = re.compile(
    r"^(feat|fix|refactor|docs|chore|spike)/[a-z0-9][a-z0-9-]*$"
)
VALID_PREFIXES = ("feat/", "fix/", "refactor/", "docs/", "chore/", "spike/")


def check_branch() -> Optional[CheckResult]:
    _, branch, _ = run(["git", "branch", "--show-current"])
    branch = branch.strip()

    if not branch:
        return None  # detached HEAD (e.g., CI checkout); naming convention not applicable

    if branch == "main":
        return CheckResult(
            "branch",
            False,
            "on main — create a feature branch first",
        )

    if not BRANCH_PATTERN.match(branch):
        prefixes = ", ".join(f"{p}<description>" for p in VALID_PREFIXES)
        return CheckResult(
            "branch",
            False,
            f"'{branch}' does not follow naming convention",
            f"Expected: {prefixes}\n"
            "Rules: prefix/ followed by lowercase letters, digits, hyphens only.",
        )

    return CheckResult("branch", True, branch)


# Dispatch rules are loaded from .work/config/dispatch-rules.json at runtime.
# Edit that file to add or modify mandatory agent requirements without changing
# this script. Patterns are matched with re.search — anchor with (^|/) or ^ to
# prevent false matches in subdirectories or vendored copies.
_DISPATCH_RULES_FILE = os.path.join(REPO_ROOT, ".work", "config", "dispatch-rules.json")


def _load_dispatch_rules() -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Load (mandatory_agents, always_required) from dispatch-rules.json.

    Raises FileNotFoundError or json.JSONDecodeError on failure.
    """
    with open(_DISPATCH_RULES_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    mandatory = [(r["pattern"], r["agents"]) for r in data.get("mandatory_agents", [])]
    always: list[str] = data.get("always_required", [])
    return mandatory, always


def _get_changed_files() -> tuple[list[str], Optional[str]]:
    """Return (changed_files, error_message).

    error_message is non-None when neither `main` nor `origin/main` exists
    locally — without that, the dispatch floor cannot be enforced and must
    surface as a hard failure (fresh-clone case where _required_agents would
    otherwise silently return [] and skip security-auditor).
    """
    for ref in ("main", "origin/main"):
        code, out, _ = run(["git", "diff", f"{ref}...HEAD", "--name-only"])
        if code == 0:
            return [f.strip() for f in out.splitlines() if f.strip()], None
    return [], (
        "cannot determine changed files — neither `main` nor `origin/main` "
        "exists locally. Run `git fetch origin main:main` and retry."
    )


def _required_agents() -> tuple[dict[str, list[str]], Optional[str]]:
    """Return ({agent: [reasons]}, error_message) for the current diff."""
    files, err = _get_changed_files()
    try:
        mandatory_agents, always_required = _load_dispatch_rules()
    except FileNotFoundError:
        return {}, (
            f"dispatch-rules.json not found at {_DISPATCH_RULES_FILE} — "
            "run `git pull` or recreate .work/config/dispatch-rules.json"
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {}, f"dispatch-rules.json malformed: {exc}"
    required: dict[str, list[str]] = {a: ["always required"] for a in always_required}
    for filepath in files:
        for pattern, agents in mandatory_agents:
            if re.search(pattern, filepath):
                for agent in agents:
                    required.setdefault(agent, []).append(filepath)
    return required, err


def check_dispatch(panel: list[str]) -> CheckResult:
    required, err = _required_agents()
    if err is not None:
        return CheckResult("dispatch", False, "cannot enforce dispatch floor", err)

    if not panel:
        agent_list = ", ".join(sorted(required))
        detail = "\n".join(
            f"  {a}: {', '.join(files[:2])}"
            for a, files in sorted(required.items())
        )
        return CheckResult(
            "dispatch",
            True,
            f"minimum panel — {len(required)} agent(s): {agent_list}",
            detail,
        )

    missing = {a: f for a, f in required.items() if a not in panel}
    if missing:
        lines = []
        for agent, files in sorted(missing.items()):
            reason = files[0] if files[0] == "always required" else ", ".join(files[:2])
            lines.append(f"  {agent}  (required by: {reason})")
        return CheckResult(
            "dispatch",
            False,
            f"{len(missing)} mandatory agent(s) missing from panel",
            "\n".join(lines),
        )

    return CheckResult(
        "dispatch",
        True,
        f"panel covers all {len(required)} mandatory agent(s)",
    )


# ---------------------------------------------------------------------------
# State backend abstraction
# ---------------------------------------------------------------------------
# The gate reads work items from whichever backend context.json specifies.
# Default is "local-file" (.work/work.json). Set "state_backend":
# "github-issues" in context.json to read from open GitHub Issues instead.
# The GitHub Issues backend expects issues with titles like "WORK-NNNN: ..."
# and treats open issues as live items.

_WORK_ITEM_ID_RE = re.compile(r"^(WORK-\d+):")


def _state_backend() -> str:
    """Return the configured state backend name (default 'local-file')."""
    context_path = os.path.join(REPO_ROOT, ".work", "context.json")
    if not os.path.exists(context_path):
        return "local-file"
    try:
        with open(context_path, encoding="utf-8") as fh:
            ctx = json.load(fh)
        return str(ctx.get("state_backend", "local-file"))
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        return "local-file"


def _load_work_items() -> tuple[set[str], Optional[str]]:
    """Return (live_item_ids, error_or_None).

    live_item_ids contains WORK-XXXX strings for all active/backlog items.
    error_or_None is set when the backend could not be read; callers should
    propagate it as a FAIL rather than silently using an empty set.
    """
    backend = _state_backend()
    if backend == "github-issues":
        return _load_work_items_github()
    return _load_work_items_local()


def _load_work_items_local() -> tuple[set[str], Optional[str]]:
    work_path = os.path.join(REPO_ROOT, ".work", "work.json")
    if not os.path.exists(work_path):
        return set(), None
    try:
        with open(work_path, encoding="utf-8") as fh:
            work = json.load(fh)
        live_ids: set[str] = set()
        for section in ("active", "backlog"):
            for item in work.get(section, []):
                live_ids.add(item.get("id", ""))
        return live_ids, None
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return set(), f"work.json malformed: {exc}"


def _load_work_items_github() -> tuple[set[str], Optional[str]]:
    if not shutil.which("gh"):
        return set(), "gh CLI not available — cannot read GitHub Issues backend"
    code, out, err = run([
        "gh", "issue", "list", "--state", "open",
        "--json", "number,title", "--limit", "200",
    ])
    if code != 0:
        return set(), f"gh issue list failed: {(err or '').strip()[:200]}"
    try:
        issues = json.loads(out) if out.strip() else []
    except json.JSONDecodeError as exc:
        return set(), f"could not parse gh issue list output: {exc}"
    live_ids: set[str] = set()
    for issue in issues:
        m = _WORK_ITEM_ID_RE.match(issue.get("title", ""))
        if m:
            live_ids.add(m.group(1))
    return live_ids, None


def check_budget() -> CheckResult:
    """Report current review panel budget tier and deferral queue depth."""
    if not os.path.exists(_BUDGET_MGR):
        return CheckResult("budget", True, "budget_manager.py not found — no tracking active")

    code, out, err = run(["python3", _BUDGET_MGR, "tier"])
    tier = out.strip() if code == 0 else "UNKNOWN"

    code2, out2, _err2 = run(["python3", _BUDGET_MGR])
    if code2 != 0:
        return CheckResult("budget", True, f"tier: {tier} (status unavailable)")

    lines = out2.strip().splitlines()
    detail = "\n".join(line for line in lines if line.strip())

    if tier == "DEFERRED":
        advisory = " — session budget exhausted; use queue"
    elif tier in ("REDUCED", "MINIMAL"):
        advisory = " — optional agents will be deferred to queue"
    else:
        advisory = ""

    return CheckResult("budget", True, f"tier: {tier}{advisory}", detail)


def check_config() -> Optional[CheckResult]:
    """Validate dispatch-rules.json against actual agent files on disk.

    Returns None (skip) when .work/ does not exist — gate-only tier installs
    have no dispatch config and the check is not applicable. Returns FAIL when
    .work/ exists but dispatch-rules.json is missing, because that indicates
    a partial / broken configuration.
    """
    work_dir = os.path.join(REPO_ROOT, ".work")
    if not os.path.isdir(work_dir):
        return None  # gate-only install — no .work/ directory

    if not os.path.exists(_DISPATCH_RULES_FILE):
        return CheckResult(
            "config", False,
            "dispatch-rules.json not found",
            f"Expected at {_DISPATCH_RULES_FILE}",
        )

    try:
        mandatory_agents, always_required = _load_dispatch_rules()
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return CheckResult("config", False, f"dispatch-rules.json malformed: {exc}")

    agents_dir = os.path.join(REPO_ROOT, ".claude", "agents")
    if not os.path.isdir(agents_dir):
        return CheckResult("config", False, ".claude/agents/ directory not found")

    on_disk = {
        os.path.splitext(f)[0]
        for f in os.listdir(agents_dir)
        if f.endswith(".md")
    }

    referenced = set(always_required)
    for _, agents in mandatory_agents:
        referenced.update(agents)

    stale = sorted(referenced - on_disk)
    issues = []
    if stale:
        issues.append("dispatch-rules.json references agents with no file:")
        issues.extend(f"  missing file: .claude/agents/{a}.md" for a in stale)

    if issues:
        return CheckResult("config", False, f"{len(stale)} stale rule(s)", "\n".join(issues))

    return CheckResult(
        "config",
        True,
        f"dispatch rules consistent ({len(referenced)} agents, {len(on_disk)} on disk)",
    )


def check_commands() -> Optional[CheckResult]:
    """Detect stale hardcoded work-item IDs in .claude/commands/.

    An ID is stale if it does not appear in the configured backend's active or
    backlog items. Reads from local-file (work.json) or github-issues backend
    per context.json. Skips when no backend data is available.
    """
    commands_dir = os.path.join(REPO_ROOT, ".claude", "commands")
    if not os.path.isdir(commands_dir):
        return None

    live_ids, load_err = _load_work_items()
    if load_err is not None:
        return CheckResult(
            "commands",
            False,
            f"cannot load work items: {load_err}",
        )
    if not live_ids and _state_backend() == "local-file":
        # local-file with no work.json — cannot validate; skip
        work_path = os.path.join(REPO_ROOT, ".work", "work.json")
        if not os.path.exists(work_path):
            return None

    stale: list[str] = []
    for fname in sorted(os.listdir(commands_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(commands_dir, fname)
        with open(fpath, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                for m in re.finditer(r"WORK-\d+", line):
                    item_id = m.group(0)
                    if item_id not in live_ids:
                        stale.append(f"  {fname}:{lineno}: {item_id} (not in backend)")

    if stale:
        return CheckResult(
            "commands",
            False,
            f"{len(stale)} stale work-item ID(s) in .claude/commands/",
            "\n".join(stale[:20]),
        )
    return CheckResult("commands", True, ".claude/commands/ has no stale work-item IDs")


def _pymarkdown_cmd() -> Optional[list[str]]:
    """Return the command prefix for pymarkdown, or None if not available."""
    for name in ("pymarkdown", "pymarkdownlnt"):
        if shutil.which(name):
            return [name]
    # Check the active virtual environment's bin directory when not on PATH
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        for name in ("pymarkdown", "pymarkdownlnt"):
            candidate = os.path.join(venv, "bin", name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return [candidate]
    # Try as a Python module with the current interpreter
    code, _, _ = run([sys.executable, "-m", "pymarkdown", "version"])
    if code == 0:
        return [sys.executable, "-m", "pymarkdown"]
    return None


_SCHEMA_VALIDATOR = os.path.join(os.path.dirname(__file__), "check_markdown_schema.py")
_SCHEMAS_FILE = os.path.join(REPO_ROOT, ".work", "config", "markdown-schemas.json")


def check_markdown_schemas() -> Optional[CheckResult]:
    """Validate markdown files against .work/config/markdown-schemas.json."""
    if not os.path.exists(_SCHEMA_VALIDATOR):
        return None
    if not os.path.exists(_SCHEMAS_FILE):
        return None

    code, out, err = run([sys.executable, _SCHEMA_VALIDATOR, "--json"])

    try:
        result = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        combined = (out + err).strip()
        return CheckResult("schemas", False, "schema validator produced unexpected output", combined[:500])

    if "error" in result:
        return CheckResult("schemas", False, result["error"])

    count = result.get("violation_count", 0)
    if not result.get("passed", True):
        violations = result.get("violations", [])
        lines = [f"  {v['file']}: [{v['schema']}] {v['message']}" for v in violations[:20]]
        return CheckResult(
            "schemas",
            False,
            f"{count} schema violation(s)",
            "\n".join(lines),
        )

    return CheckResult("schemas", True, "all markdown files pass schema validation")


def check_markdown() -> Optional[CheckResult]:
    cmd = _pymarkdown_cmd()
    if cmd is None:
        return None
    config = os.path.join(REPO_ROOT, ".pymarkdown.json")
    config_args = ["--config", config] if os.path.exists(config) else []
    # Use relative paths — pymarkdown's -e exclusion only works with relative paths.
    _targets = [
        "docs", ".claude", ".work", "config",
        "README.md", "CLAUDE.md",
        os.path.join(".github", "PULL_REQUEST_TEMPLATE.md"),
    ]
    scan_targets = [t for t in _targets if os.path.exists(os.path.join(REPO_ROOT, t))]
    if not scan_targets:
        return None

    # Always exclude .work/reviews — generated adversarial review artifacts with intentionally long
    # lines. pymarkdown handles non-existent exclusion paths gracefully (exit 0).
    exclude_args = ["-e", ".work/reviews"]
    code, out, err = run(cmd + config_args + ["scan", "--recurse"] + exclude_args + scan_targets)
    if code != 0:
        combined = (out + err).strip()
        lines = combined.splitlines()[:30]
        return CheckResult("markdown", False, "pymarkdown violations found", "\n".join(lines))
    return CheckResult("markdown", True, "pymarkdown clean")


def check_lint() -> Optional[CheckResult]:
    config = _load_hedl_config()
    if config is not None and "verify" in config:
        spec = config["verify"].get("lint")
        if spec is None:
            return None  # [verify] present but lint not declared — skip
        return _run_declared_check("lint", spec, _get_gate_timeout(config), _verify_allowlist(config))
    # No [verify] — built-in Python default profile
    pyproject = os.path.join(REPO_ROOT, "pyproject.toml")
    ruff_toml = os.path.join(REPO_ROOT, "ruff.toml")
    if not os.path.exists(pyproject) and not os.path.exists(ruff_toml):
        return None  # no ruff config — check not applicable
    if not shutil.which("ruff"):
        return CheckResult("lint", False, "ruff not found — uv sync  or  pip install ruff")

    code, out, err = run(["ruff", "check", "."])
    if code != 0:
        return CheckResult("lint", False, "ruff check failed", (out + err).strip())
    return CheckResult("lint", True, "ruff clean")


def check_types() -> Optional[CheckResult]:
    config = _load_hedl_config()
    if config is not None and "verify" in config:
        spec = config["verify"].get("types")
        if spec is None:
            return None  # [verify] present but types not declared — skip
        return _run_declared_check("types", spec, _get_gate_timeout(config), _verify_allowlist(config))
    # No [verify] — built-in Python default profile
    src_candidates = ["src", "lib", "app", "skill/hedl/scripts", "tests", "skill/hedl/tests"]
    # Skip dirs with no .py files (avoids mypy exit-code 2 on empty/cache-only dirs).
    targets = [
        d for d in src_candidates
        if os.path.isdir(os.path.join(REPO_ROOT, d))
        and any(f.endswith(".py") for f in os.listdir(os.path.join(REPO_ROOT, d)))
    ]
    if not targets:
        return None  # no source directories — check not applicable
    if not shutil.which("mypy"):
        return CheckResult("types", False, "mypy not found — uv sync  or  pip install mypy")

    code, out, err = run(["mypy", "--strict"] + targets)
    if code != 0:
        combined = (out + err).strip()
        # show only error lines, cap at 20
        lines = [ln for ln in combined.splitlines() if ": error:" in ln][:20]
        return CheckResult("types", False, "mypy errors", "\n".join(lines))
    return CheckResult("types", True, "mypy clean")


def check_tests() -> Optional[CheckResult]:
    config = _load_hedl_config()
    if config is not None and "verify" in config:
        spec = config["verify"].get("test")  # hedl.toml key is "test"; display name stays "tests"
        if spec is None:
            return None  # [verify] present but test not declared — skip
        return _run_declared_check("tests", spec, _get_gate_timeout(config), _verify_allowlist(config))
    # No [verify] — built-in Python default profile
    tests_candidates = ["tests", "skill/hedl/tests"]
    has_tests = any(
        os.path.isdir(os.path.join(REPO_ROOT, d))
        and any(f.endswith(".py") for f in os.listdir(os.path.join(REPO_ROOT, d)))
        for d in tests_candidates
    )
    if not has_tests:
        return None  # no tests directory — check not applicable
    if not shutil.which("pytest"):
        return CheckResult("tests", False, "pytest not found — uv sync  or  pip install pytest")

    code, out, err = run(["pytest", "--tb=short", "-q"])
    if code != 0:
        combined = (out + err).strip()
        lines = combined.splitlines()[-30:]
        return CheckResult("tests", False, "pytest failures", "\n".join(lines))
    # extract summary line
    summary_lines = [ln for ln in out.splitlines() if "passed" in ln or "failed" in ln]
    summary = summary_lines[-1] if summary_lines else "passed"
    return CheckResult("tests", True, summary)


def check_dependabot() -> CheckResult:
    """Check for open Dependabot security alerts. Skips gracefully if not configured."""
    if not shutil.which("gh"):
        return CheckResult("dependabot", True, "gh CLI not available — skipping")

    code, repo_out, _ = run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]
    )
    if code != 0:
        return CheckResult("dependabot", True, "could not determine repo — skipping")

    repo = repo_out.strip()
    if not re.match(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", repo):
        return CheckResult("dependabot", False, f"unexpected repo name format '{repo}' — cannot validate Dependabot alerts")
    code, out, err = run([
        "gh", "api", f"/repos/{repo}/dependabot/alerts",
        "--paginate",
        "--jq", '.[] | select(.state == "open") | .number',
    ])
    if code != 0:
        err_text = (err or "").strip()
        err_low = err_text.lower()
        # Any 403 on the Dependabot API means the token cannot access it (either
        # GitHub App limitation or org-level restriction). Caller can't fix with
        # `gh auth login` — skip rather than fail. Run locally with full auth.
        if "403" in err_low:
            return CheckResult("dependabot", True, "Dependabot check skipped — token lacks access (run locally with gh auth)")
        if any(h.lower() in err_low for h in _GH_AUTH_HINTS):
            return CheckResult(
                "dependabot", False,
                "gh CLI not authenticated — run `gh auth login`",
                err_text[:200],
            )
        # 404 = Dependabot not configured; treat as no alerts
        if "404" in err_text or "not found" in err_low:
            return CheckResult("dependabot", True, "Dependabot not configured — no alerts")
        return CheckResult("dependabot", False, "Dependabot check failed", err_text[:200])

    open_lines = [ln for ln in out.splitlines() if ln.strip()]
    count = len(open_lines)

    if count > 0:
        code2, detail_out, _ = run([
            "gh", "api", f"/repos/{repo}/dependabot/alerts",
            "--paginate",
            "--jq",
            '.[] | select(.state == "open") | .dependency.package.name + " (" + .security_advisory.severity + ")"',
        ])
        detail_lines = (detail_out.strip().splitlines() if code2 == 0 else [])[:5]
        detail = "\n".join(detail_lines)
        return CheckResult(
            "dependabot", False,
            f"{count} open Dependabot alert(s) — bump affected dependencies",
            detail,
        )

    return CheckResult("dependabot", True, "no open Dependabot alerts")


_THREADS_QUERY = (
    "query($owner:String!,$repo:String!,$pr:Int!){"
    "repository(owner:$owner,name:$repo){"
    "pullRequest(number:$pr){"
    "reviewThreads(first:100){nodes{id isResolved}}}}}"
)


def check_pr_threads(pr_number: int) -> CheckResult:
    """Check for unresolved PR review threads via GitHub GraphQL."""
    if not shutil.which("gh"):
        return CheckResult("threads", True, "gh CLI not available — skipping")

    code, out, _ = run(
        ["gh", "repo", "view", "--json", "owner,name",
         "--jq", ".owner.login + \"/\" + .name"]
    )
    if code != 0:
        return CheckResult("threads", True, "could not determine repo — skipping")

    owner, _, repo_name = out.strip().partition("/")
    if not owner or not repo_name:
        return CheckResult("threads", True, "could not parse repo owner/name — skipping")

    code, out, err = run([
        "gh", "api", "graphql",
        "-f", f"query={_THREADS_QUERY}",
        "-f", f"owner={owner}",
        "-f", f"repo={repo_name}",
        "-F", f"pr={pr_number}",
        "--jq",
        "[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length",
    ])
    if code != 0:
        err_text = (err or "").strip()
        err_low = err_text.lower()
        # Any 403 means the token cannot access the GraphQL API — skip rather
        # than fail so CI is not permanently blocked by a permission restriction.
        if "403" in err_low:
            return CheckResult("threads", True, "threads check skipped — token lacks access (run locally with gh auth)")
        if any(h.lower() in err_low for h in _GH_AUTH_HINTS):
            return CheckResult(
                "threads", False,
                "gh CLI not authenticated — run `gh auth login`",
                err_text[:200],
            )
        return CheckResult("threads", False, "could not check PR threads — failing closed", err_text[:200])

    try:
        count = int(out.strip())
    except ValueError:
        return CheckResult("threads", False, "could not parse thread response — failing closed")

    if count > 0:
        return CheckResult(
            "threads", False,
            f"{count} unresolved PR review thread(s) — fix or rebut each before merge",
        )

    return CheckResult("threads", True, f"no unresolved threads on PR #{pr_number}")


def check_template(pr_number: int) -> CheckResult:
    code, body, err = run(
        ["gh", "pr", "view", str(pr_number), "--json", "body", "--jq", ".body"]
    )
    if code != 0:
        return CheckResult(
            "template",
            False,
            f"could not fetch PR #{pr_number}",
            err.strip(),
        )

    env = os.environ.copy()
    env["PR_BODY"] = body.strip().replace("\x00", "")
    result = subprocess.run(
        ["python3", os.path.join(REPO_ROOT, ".github/scripts/check_pr_template.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return CheckResult(
            "template", False, "PR template incomplete", result.stdout.strip()
        )
    return CheckResult("template", True, f"PR #{pr_number} template valid")


_GH_AUTH_HINTS = ("authentication", "authenticate", "HTTP 401", "HTTP 403", "gh auth login")
_GH_RATE_HINTS = ("API rate limit", "secondary rate limit", "rate limit exceeded")


def _should_poll_ci(only: Optional[str], pr: Optional[int]) -> bool:
    """Whether to run the ci check. It polls the PR's own check-runs, which
    include this gate's matrix jobs — so running it as part of the gate
    (default mode) is self-referential and can never pass. Per the documented
    contract it runs only on an explicit ``--check ci`` and requires ``--pr``.
    """
    return only == "ci" and pr is not None


def check_ci(pr_number: int) -> CheckResult:
    """Inspect PR CI checks.

    Uses the structured JSON output instead of parsing tab-delimited text
    (the `gh pr checks` text format was treating CANCELLED / TIMED_OUT /
    STARTUP_FAILURE as PASS).

    Distinguishes auth/rate-limit failure from "no checks found".
    """
    if not shutil.which("gh"):
        return CheckResult("ci", False, "gh CLI not available")

    code, out, err = run([
        "gh", "pr", "checks", str(pr_number),
        "--json", "name,state,bucket",
    ])
    if code != 0:
        err_text = (err or "").strip()
        err_low = err_text.lower()
        if any(h.lower() in err_low for h in _GH_AUTH_HINTS):
            return CheckResult(
                "ci", False,
                "gh CLI not authenticated — run `gh auth login`",
                err_text[:500],
            )
        if any(h.lower() in err_low for h in _GH_RATE_HINTS):
            return CheckResult(
                "ci", False,
                "GitHub API rate-limited — retry later",
                err_text[:500],
            )
        return CheckResult("ci", False, "gh pr checks failed", err_text[:500])

    try:
        checks = json.loads(out) if out.strip() else []
    except json.JSONDecodeError as exc:
        return CheckResult("ci", False, "could not parse gh JSON", str(exc))

    if not checks:
        return CheckResult(
            "ci", False,
            "no CI checks found — PR may not exist or checks haven't started",
        )

    # gh's `bucket` field collapses {COMPLETED.SUCCESS, COMPLETED.NEUTRAL,
    # COMPLETED.SKIPPED} -> "pass"; COMPLETED.{FAILURE, CANCELLED, TIMED_OUT,
    # ACTION_REQUIRED, STARTUP_FAILURE} -> "fail"; everything in-flight -> "pending".
    failing = [c for c in checks if c.get("bucket") == "fail"]
    pending = [c for c in checks if c.get("bucket") == "pending"]

    if failing:
        names = ", ".join(f"{c.get('name', '?')}[{c.get('state', '?')}]" for c in failing[:5])
        return CheckResult(
            "ci", False, f"{len(failing)} check(s) failing", names,
        )
    if pending:
        names = ", ".join(c.get("name", "?") for c in pending[:5])
        return CheckResult(
            "ci", False, f"{len(pending)} check(s) still running", names,
        )

    return CheckResult("ci", True, f"all {len(checks)} checks green for PR #{pr_number}")


def check_streams(streams: list[str]) -> CheckResult:
    """Validate no file overlap across parallel worktree streams.

    Each stream is a branch name. The check diffs each branch against main
    (falling back to origin/main) and fails if any file is touched by more
    than one stream. Gate-only installs that don't use parallel worktrees
    never pass --streams, so this check never runs for them.
    """
    if not streams:
        return CheckResult("streams", True, "no parallel streams specified")

    stream_files: dict[str, list[str]] = {}
    for branch in streams:
        code, out, err = run(["git", "diff", f"main...{branch}", "--name-only"])
        if code != 0:
            code, out, _ = run(["git", "diff", f"origin/main...{branch}", "--name-only"])
            if code != 0:
                return CheckResult(
                    "streams", False,
                    f"could not diff stream '{branch}' against main",
                    (err or "").strip()[:200],
                )
        stream_files[branch] = [f.strip() for f in out.splitlines() if f.strip()]

    file_owners: dict[str, list[str]] = {}
    for branch, files in stream_files.items():
        for f in files:
            file_owners.setdefault(f, []).append(branch)

    conflicts = {f: owners for f, owners in file_owners.items() if len(owners) > 1}
    if conflicts:
        lines = [
            f"  {f}: {', '.join(sorted(owners))}"
            for f, owners in sorted(conflicts.items())[:20]
        ]
        return CheckResult(
            "streams", False,
            f"{len(conflicts)} file(s) touched by multiple streams — parallel writes not allowed",
            "\n".join(lines),
        )

    total = sum(len(fs) for fs in stream_files.values())
    return CheckResult(
        "streams", True,
        f"{len(streams)} stream(s) clean, {total} total file(s) changed, no overlap",
    )


CLI_SPEC: dict[str, Any] = {
    "name": "am_i_done",
    "script": "am_i_done.py",
    "description": "Deterministic completion gate — runs all applicable checks and exits 0 only when all pass.",
    "invocation": "python3 .github/scripts/am_i_done.py",
    "commands": [
        {
            "name": "default",
            "description": "Run applicable checks (all, or one with --check)",
            "args": [
                {
                    "flag": "--check",
                    "type": "str",
                    "required": False,
                    "choices": [
                        "git", "branch", "dispatch", "config", "commands",
                        "schemas", "markdown", "lint", "types", "tests",
                        "template", "dependabot", "threads", "ci",
                        "budget", "streams", "skill-meta", "docs-index",
                    ],
                    "help": "Run only this check",
                },
                {
                    "flag": "--pr",
                    "type": "int",
                    "required": False,
                    "help": "PR number for template, dependabot, threads, and ci checks",
                },
                {
                    "flag": "--panel",
                    "type": "str",
                    "required": False,
                    "help": "Comma-separated list of agents dispatched (for dispatch check)",
                },
                {
                    "flag": "--streams",
                    "type": "str",
                    "required": False,
                    "help": "Comma-separated branch names for parallel worktree file-scoping check",
                },
                {
                    "flag": "--json",
                    "type": "bool",
                    "required": False,
                    "help": "Machine-readable JSON output of check results",
                },
            ],
            "output": (
                "Exits 0 if all checks pass, 1 if any fail, 2 if no checks apply. "
                "--json emits {passed, checks:[{name, passed, message, detail}]}."
            ),
        },
    ],
}


def check_skill_metadata() -> Optional[CheckResult]:
    """Check that SKILL.md's generated section matches script --schema output."""
    if not os.path.exists(_GEN_METADATA):
        return None  # not in skill dev context — skip gracefully

    code, out, err = run([sys.executable, _GEN_METADATA, "--check"])
    if code == 0:
        return CheckResult("skill-meta", True, "SKILL.md deterministic section is up to date")

    combined = (out + err).strip()
    lines = combined.splitlines()[:20]
    return CheckResult(
        "skill-meta",
        False,
        "SKILL.md deterministic section is stale or has invalid references",
        "\n".join(lines),
    )


def check_docs_index() -> CheckResult:
    """Fail if any human-facing markdown doc is not reachable by link from README.md.

    Scope: docs/**/*.md, skill/hedl/references/*.md, skill/hedl/SKILL.md, CHANGELOG.md.
    Symlinks are resolved (os.path.realpath) so a docs/ symlink covering a references/
    file counts as one entry -- linking either path satisfies both.
    Operational trees (.github/, .claude/, .work/, skill/hedl/agents|commands|templates|
    workflows|scripts|integrations) are excluded.
    """
    readme_path = os.path.join(REPO_ROOT, "README.md")
    if not os.path.exists(readme_path):
        return CheckResult("docs-index", False, "README.md not found")

    with open(readme_path, encoding="utf-8") as fh:
        readme_text = fh.read()

    _link_re = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
    linked_real: set[str] = set()
    for m in _link_re.finditer(readme_text):
        href = m.group(1).split("#")[0].strip()
        if not href or href.startswith(("http://", "https://", "mailto:")):
            continue
        abs_path = os.path.normpath(os.path.join(REPO_ROOT, href))
        if os.path.exists(abs_path):
            linked_real.add(os.path.realpath(abs_path))

    in_scope: list[str] = []
    docs_dir = os.path.join(REPO_ROOT, "docs")
    if os.path.isdir(docs_dir):
        for dirpath, _dirs, filenames in os.walk(docs_dir):
            for fn in sorted(filenames):
                if fn.endswith(".md"):
                    in_scope.append(os.path.join(dirpath, fn))
    refs_dir = os.path.join(REPO_ROOT, "skill", "hedl", "references")
    if os.path.isdir(refs_dir):
        for fn in sorted(os.listdir(refs_dir)):
            if fn.endswith(".md"):
                in_scope.append(os.path.join(refs_dir, fn))
    skill_md = os.path.join(REPO_ROOT, "skill", "hedl", "SKILL.md")
    if os.path.exists(skill_md):
        in_scope.append(skill_md)
    changelog = os.path.join(REPO_ROOT, "CHANGELOG.md")
    if os.path.exists(changelog):
        in_scope.append(changelog)

    orphans: list[str] = []
    seen_real: set[str] = set()
    for doc in in_scope:
        real = os.path.realpath(doc)
        if real in seen_real:
            continue
        seen_real.add(real)
        if real not in linked_real:
            orphans.append("  " + os.path.relpath(doc, REPO_ROOT))

    if orphans:
        return CheckResult(
            "docs-index",
            False,
            f"{len(orphans)} doc(s) not linked from README.md",
            "\n".join(orphans),
        )
    return CheckResult("docs-index", True, "all human-facing docs reachable from README.md")


def main() -> int:
    if "--schema" in sys.argv:
        print(json.dumps(CLI_SPEC, indent=2))
        return 0

    if "--version" in sys.argv:
        print(_hedl_version())
        return 0

    parser = argparse.ArgumentParser(description="Deterministic completion gate")
    _check_spec = next(a for a in CLI_SPEC["commands"][0]["args"] if a["flag"] == "--check")
    parser.add_argument(
        "--check",
        choices=_check_spec["choices"],
        help=_check_spec["help"],
    )
    parser.add_argument("--pr", type=int, help="PR number for template and CI checks")
    parser.add_argument(
        "--panel",
        help="Comma-separated list of agents dispatched for this review (for dispatch check)",
    )
    parser.add_argument(
        "--streams",
        help="Comma-separated branch names for parallel worktree file-scoping check",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = parser.parse_args()

    report = Report()

    def maybe_add(result: Optional[CheckResult]) -> None:
        if result is not None:
            report.results.append(result)

    only = args.check

    panel = [a.strip() for a in args.panel.split(",") if a.strip()] if args.panel else []
    streams = [s.strip() for s in args.streams.split(",") if s.strip()] if args.streams else []

    if not only or only == "budget":
        maybe_add(check_budget())
    if not only or only == "git":
        maybe_add(check_git())
    if not only or only == "branch":
        maybe_add(check_branch())
    if only == "dispatch" or (args.panel and not only):
        maybe_add(check_dispatch(panel))
    if not only or only == "config":
        maybe_add(check_config())
    if not only or only == "commands":
        maybe_add(check_commands())
    if not only or only == "schemas":
        maybe_add(check_markdown_schemas())
    if not only or only == "markdown":
        maybe_add(check_markdown())
    if not only or only == "lint":
        maybe_add(check_lint())
    if not only or only == "types":
        maybe_add(check_types())
    if not only or only == "tests":
        maybe_add(check_tests())
    if not only or only == "skill-meta":
        maybe_add(check_skill_metadata())
    if not only or only == "docs-index":
        maybe_add(check_docs_index())
    # Extra declared checks: any [verify] key that is not a standard check name.
    # These only run in the default (no --check filter) mode.
    if not only:
        _cfg = _load_hedl_config()
        if _cfg and "verify" in _cfg:
            _gate_to = _get_gate_timeout(_cfg)
            _allowed = _verify_allowlist(_cfg)
            _STANDARD_VERIFY_KEYS = {"lint", "types", "test"}
            for _name, _spec in _cfg["verify"].items():
                if _name not in _STANDARD_VERIFY_KEYS:
                    maybe_add(_run_declared_check(_name, _spec, _gate_to, _allowed))
    if (not only or only == "template") and args.pr:
        maybe_add(check_template(args.pr))
    if (not only or only == "dependabot") and args.pr:
        maybe_add(check_dependabot())
    if (not only or only == "threads") and args.pr:
        maybe_add(check_pr_threads(args.pr))
    if _should_poll_ci(only, args.pr):
        maybe_add(check_ci(args.pr))
    if only == "streams" or (streams and not only):
        maybe_add(check_streams(streams))

    if not report.results:
        # Distinct exit code so callers can tell "verified clean" from
        # "nothing to verify".
        print("No applicable checks found. Nothing to validate.", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        report.print_human()

    _append_gate_insight(report)

    return 0 if report.passed else 1


def _append_gate_insight(report: Report) -> None:
    """Append a gate_run event to .work/insights/events.jsonl if insights are enabled."""
    config = _load_hedl_config()
    if config is None:
        return
    if not config.get("insights", {}).get("enabled", False):
        return

    import datetime as _dt
    insights_dir = os.path.join(REPO_ROOT, ".work", "insights")
    events_file = os.path.join(insights_dir, "events.jsonl")
    try:
        os.makedirs(insights_dir, exist_ok=True)
        tier = "unknown"
        marker = os.path.join(REPO_ROOT, ".hedl-tier")
        if os.path.exists(marker):
            try:
                tier = json.loads(open(marker).read()).get("tier", "unknown")
            except Exception:
                pass
        checks: dict[str, str] = {}
        overridden: list[str] = []
        for r in report.results:
            checks[r.name] = "pass" if r.passed else "fail"
        event = {
            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "type": "gate_run",
            "tier": tier,
            "checks": checks,
            "overridden": overridden,
        }
        with open(events_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception:
        pass  # insights are best-effort; never block the gate


if __name__ == "__main__":
    sys.exit(main())
