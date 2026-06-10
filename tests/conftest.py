"""Put the src-layout package on sys.path for the test run.

The shipped plugin lives in `plugin/`; the engine package is `plugin/src/lume`.
plugin/bin/lume adds its sibling `src` to the path at runtime; for tests (which
stay at the repo root, outside the shipped plugin), this conftest does the same
at collection time so `from lume import ...` resolves without an editable
install. Stdlib-only - no packaging toolchain required to run the suite.

This file lives in tests/; the package is one level up at <repo>/plugin/src.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "src"))
