import unittest

from lume import frontmatter


class FrontmatterTest(unittest.TestCase):
    def test_parse_extracts_meta_and_body(self):
        text = "---\nid: 001\nphase: proposed\n---\n# Title\n\nbody line\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta, {"id": "001", "phase": "proposed"})
        self.assertEqual(body, "# Title\n\nbody line\n")  # body carried through verbatim

    def test_no_fence_returns_empty_meta_and_whole_text(self):
        text = "# just a heading\nno frontmatter\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta, {})
        self.assertEqual(body, text)

    def test_round_trip_is_exact(self):
        # Invariant: render then parse reproduces meta + body exactly (body verbatim,
        # trailing newline included), and re-rendering is byte-identical.
        meta = {"id": "002", "type": "build", "phase": "accepted", "opened": "2026-06-09"}
        body = "# Iteration 002 - x\n\n## DoD\n- [ ] thing\n"
        once = frontmatter.render(meta, body)
        meta2, body2 = frontmatter.parse(once)
        self.assertEqual(meta2, meta)
        self.assertEqual(body2, body)
        self.assertEqual(frontmatter.render(meta2, body2), once)

    def test_parse_render_reproduces_original_file(self):
        original = (
            "---\nid: 003\ntype: build\nphase: working\nopened: 2026-06-09\n---\n"
            "# Iteration 003\n\n## DoD\n- [ ] x\n"
        )
        meta, body = frontmatter.parse(original)
        self.assertEqual(frontmatter.render(meta, body), original)


if __name__ == "__main__":
    unittest.main()
