import unittest

from lume.iteration import Iteration
from lume.snapshot import build_snapshot


def _it(id: int, phase: str, title: str, verdict: str | None = None) -> Iteration:
    body = f"# Iteration {id:03d} - {title}\n\n## Verdict\n"
    if verdict:
        body += verdict + "\n"
    return Iteration(id=id, type="build", phase=phase, opened="2026-06-01", body=body)


EXISTING = (
    "# build-lume - snapshot\n\n"
    "Updated: 2026-06-01 (stale)\n\n"
    "## Done\n- old done\n\n"
    "## Now\n- old now\n\n"
    "## Next\n- keep me\n- and me\n"
)


class SnapshotTest(unittest.TestCase):
    def _iterations(self):
        return [
            _it(1, "accepted", "Runnable orientation", "2026-06-09 | ACCEPTED"),
            _it(2, "accepted", "Engine module", "2026-06-09 | ACCEPTED"),
            _it(3, "working", "Recorder"),
        ]

    def test_done_lists_accepted_in_order_with_titles_and_dates(self):
        out = build_snapshot(EXISTING, self._iterations(), "2026-06-10")
        self.assertIn("- 001 Runnable orientation (accepted 2026-06-09)", out)
        self.assertIn("- 002 Engine module (accepted 2026-06-09)", out)
        done_section = out.split("## Done")[1].split("## Now")[0]
        self.assertNotIn("003", done_section)  # 003 not accepted -> not in Done

    def test_now_shows_latest_iteration(self):
        out = build_snapshot(EXISTING, self._iterations(), "2026-06-10")
        self.assertIn("## Now\n- 003 Recorder - phase working", out)

    def test_updated_line_uses_injected_date_and_latest(self):
        out = build_snapshot(EXISTING, self._iterations(), "2026-06-10")
        self.assertIn("Updated: 2026-06-10 (iteration 003 working)", out)

    def test_next_section_preserved_verbatim(self):
        out = build_snapshot(EXISTING, self._iterations(), "2026-06-10")
        self.assertIn("## Next\n- keep me\n- and me", out)
        self.assertNotIn("old done", out)
        self.assertNotIn("old now", out)

    def test_default_next_when_absent(self):
        existing = "# s\n\nUpdated: x\n\n## Done\n- d\n\n## Now\n- n\n"
        out = build_snapshot(existing, self._iterations(), "2026-06-10")
        self.assertIn("## Next\n- (add next steps)", out)

    def test_idempotent(self):
        once = build_snapshot(EXISTING, self._iterations(), "2026-06-10")
        twice = build_snapshot(once, self._iterations(), "2026-06-10")
        self.assertEqual(once, twice)

    def test_accepted_without_verdict_line_omits_date(self):
        its = [_it(1, "accepted", "No verdict line")]
        out = build_snapshot(EXISTING, its, "2026-06-10")
        self.assertIn("- 001 No verdict line\n", out)
        self.assertNotIn("(accepted", out)

    def test_no_iterations(self):
        out = build_snapshot(EXISTING, [], "2026-06-10")
        self.assertIn("- (nothing accepted yet)", out)
        self.assertIn("- (no iterations yet)", out)


class IterationTitleAndAcceptedTest(unittest.TestCase):
    def test_title_parsed_from_heading(self):
        self.assertEqual(_it(4, "working", "Some thing").title, "Some thing")

    def test_accepted_on_reads_last_accepted_line(self):
        it = _it(1, "accepted", "x", "2026-06-09 | REJECTED | bad\n2026-06-10 | ACCEPTED")
        self.assertEqual(it.accepted_on(), "2026-06-10")

    def test_accepted_on_none_when_absent(self):
        self.assertIsNone(_it(1, "working", "x").accepted_on())


if __name__ == "__main__":
    unittest.main()
