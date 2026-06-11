"""Context: the parsed-input value object threaded to every verb handler.

main() parses flags + selects the backing, then builds one Context and hands it
to the matching handler. Handlers read their inputs off it and emit through its
ok/fail/out helpers, so a verb's parse->action->output reads as one unit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..repository import Repository
from ..workstream import Workstream
from .io import _fail, _json_out, _ok


@dataclass
class Context:
    repo: Repository
    cmd: str
    rest: list[str]          # argv with global/value flags removed
    arg: str                 # rest[2] stripped, or "" - the primary positional
    json_mode: bool
    target: str | None       # -w/--workstream value
    opt_type: str | None
    opt_context: str | None
    opt_tag: str | None
    opt_new: bool = False
    opt_existing: bool = False
    opt_charter: list[str] = field(default_factory=list)  # repeatable --charter globs

    def require_ws(self) -> Workstream:
        """Resolve the targeted workstream (raises LumeError, caught by dispatch)."""
        return self.repo.workstream(self.target)

    def ok(self, data: dict, *human_lines: str) -> None:
        _ok(self.json_mode, data, *human_lines)

    def fail(self, code: str, message: str) -> None:
        _fail(self.json_mode, code, message)

    def out(self, value: object) -> None:
        _json_out(value)
