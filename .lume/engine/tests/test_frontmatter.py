import unittest

from lume import frontmatter


class FrontmatterTest(unittest.TestCase):
    def test_parse_extracts_meta_and_body(self):
        text = "---\nid: 001\nphase: proposed\n---\n# Title\n\nbody line\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta, {"id": "001", "phase": "proposed"})
        self.assertEqual(body, "# Title\n\nbody line")  # splitlines drops the trailing newline

    def test_no_fence_returns_empty_meta_and_whole_text(self):
        text = "# just a heading\nno frontmatter\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta, {})
        self.assertEqual(body, text)

    def test_round_trip_is_stable(self):
        # Invariant: rendering then parsing reproduces meta + body exactly, and
        # re-rendering is identical. (splitlines drops a trailing newline, so the
        # canonical body carried through the cycle has none.)
        meta = {"id": "002", "type": "build", "phase": "accepted", "opened": "2026-06-09"}
        body = "# Iteration 002 - x\n\n## DoD\n- [ ] thing"
        once = frontmatter.render(meta, body)
        meta2, body2 = frontmatter.parse(once)
        self.assertEqual(meta2, meta)
        self.assertEqual(body2, body)
        self.assertEqual(frontmatter.render(meta2, body2), once)


if __name__ == "__main__":
    unittest.main()
