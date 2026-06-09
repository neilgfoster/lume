"""Typed errors so the CLI can map each failure to a clear message + exit code."""


class LumeError(Exception):
    """Base for all engine errors the CLI is expected to handle."""


class NoLumeDirError(LumeError):
    """No `.lume/` directory found walking up from the start path."""


class NoWorkstreamError(LumeError):
    """A `.lume/` exists but holds no resolvable workstream."""


class GateError(LumeError):
    """A control-flow gate refused a transition (e.g. opening over an open iteration)."""
