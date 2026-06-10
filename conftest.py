"""Put the src-layout package on sys.path for the test run.

The engine package lives at `src/lume` (src layout). bin/lume adds `src` to the
path at runtime; for tests, this root conftest does the same at collection time
so `from lume import ...` resolves without an editable install. Stdlib-only - no
packaging toolchain required to run the suite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
