"""The lume CLI, organised as a package by concern:

- catalog: the verb catalog (single source of truth for verbs + USAGE)
- flags:   argv flag parsing
- io:      error/success emitters + human/JSON renderers
- app:     main() dispatch

This __init__ re-exports the public surface so `from lume.cli import main`,
`lume.cli._CATALOG`, `lume.cli._VERB_NAMES`, and `from lume import cli` keep
working unchanged.
"""
from __future__ import annotations

from .app import main
from .catalog import _CATALOG, _VERB_NAMES

__all__ = ["main", "_CATALOG", "_VERB_NAMES"]
