import datetime
import tempfile
import unittest
from pathlib import Path

from lume import migrate, state
from lume.clock import FixedClock
from lume.repository import Repository

# An iteration body with REAL verdict stamps plus PROSE that merely mentions
# ACCEPTED/REJECTED - the strict parser must capture only the stamps.
_ITER_BODY = """# Iteration 001 - Demo

## DoD
- [x] reject requires a reason, appending `YYYY-MM-DD | REJECTED | <reason>`.

## Self-review
- Attempt 1 REJECTED then redone; this line must NOT become a verdict.

## Verdict
(operator: accept / reject + reasons)
2026-06-09 | REJECTED | DoD too vague
2026-06-09 | ACCEPTED
"""

_OBJECTIVE = "---\nstatus: closed\n---\n# Demo Workstream\n\nDo the demo thing.\n"
_ITER_FILE = "---\nid: 001\ntype: execution\nphase: accepted\nopened: 2026-06-09\n---\n" + _ITER_BODY
_PLAN = """# demo - plan

## Items
- P1 | execution | iter:001 | committed | the one item
- (was P9) something deferred in prose, not a real item
"""


def _make_workstream(root: Path) -> None:
    ws = root / ".lume" / "workstreams" / "demo"
    (ws / "iterations").mkdir(parents=True)
    (ws / "objective.md").write_text(_OBJECTIVE)
    (ws / "iterations" / "001.md").write_text(_ITER_FILE)
    (ws / "plan.md").write_text(_PLAN)


def _repo(root: Path) -> Repository:
    return Repository(root, FixedClock(datetime.date(2026, 6, 9)))


class VerdictParsingTest(unittest.TestCase):
    def test_only_real_stamps_are_captured(self):
        verdicts = migrate.parse_verdicts(_ITER_BODY)
        self.assertEqual(
            verdicts,
            [
                {"date": "2026-06-09", "verdict": "rejected", "reason": "DoD too vague"},
                {"date": "2026-06-09", "verdict": "accepted", "reason": None},
            ],
        )

    def test_prose_mentions_are_not_captured(self):
        # Two stamps in the body; the DoD + self-review prose mention the words
        # but must not inflate the count.
        self.assertEqual(len(migrate.parse_verdicts(_ITER_BODY)), 2)


class LegacyTypeTest(unittest.TestCase):
    def test_legacy_build_type_normalises_to_execution(self):
        from lume.iteration import Iteration

        it = Iteration.from_text(
            "---\nid: 001\ntype: build\nphase: accepted\nopened: 2026-06-09\n---\n"
            "# Iteration 001 - x\n\n2026-06-09 | ACCEPTED\n"
        )
        self.assertEqual(migrate._iteration_entity(it)["type"], "execution")


class BuildDocTest(unittest.TestCase):
    def test_built_doc_matches_markdown_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_workstream(root)
            repo = _repo(root)
            written = migrate.migrate_all(repo, root / ".lume")
            self.assertEqual(written, ["demo"])

            doc = repo.load_state("demo")  # load re-validates
            self.assertEqual(doc["workstream"]["slug"], "demo")
            self.assertEqual(doc["workstream"]["title"], "Demo Workstream")
            self.assertEqual(doc["workstream"]["status"], "closed")
            self.assertEqual(len(doc["iterations"]), 1)
            self.assertEqual(doc["iterations"][0]["phase"], "accepted")
            self.assertEqual(len(doc["iterations"][0]["verdicts"]), 2)
            # Only the real P-item line is parsed, not the "(was P9)" prose.
            self.assertEqual([p["id"] for p in doc["plan"]], ["P1"])
            self.assertEqual(doc["plan"][0]["iter"], 1)


class IdempotencyTest(unittest.TestCase):
    def test_second_migrate_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_workstream(root)
            repo = _repo(root)
            migrate.migrate_all(repo, root / ".lume")
            first = (root / ".lume" / "workstreams" / "demo" / state.STATE_FILE).read_text()
            migrate.migrate_all(repo, root / ".lume")
            second = (root / ".lume" / "workstreams" / "demo" / state.STATE_FILE).read_text()
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
