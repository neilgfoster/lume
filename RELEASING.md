# Releasing lume

lume ships as a Claude Code plugin from this git repo's `plugin/` directory.
There is no PyPI package and no build artifact to upload: **the pinnable
artifact is a git tag.** A release is therefore just a verified, tagged commit
plus a GitHub release pointing at it.

`plugin/.claude-plugin/plugin.json` is the **single version of record**.
`pyproject.toml` only echoes it (guarded by `tests/test_version_consistency.py`),
and a release tag must equal `v<that version>` (guarded by
`tools/check_release_tag.py`).

## Cut a release (operator action)

1. **Bump the version** in `plugin/.claude-plugin/plugin.json` (semver).
2. **Run the suite** - it includes the version-consistency check:
   ```
   python -m pytest -q
   ```
3. **Verify the tag you intend to push** matches the version:
   ```
   python tools/check_release_tag.py vX.Y.Z
   ```
4. **Commit, tag, push** (the tag name must be `vX.Y.Z`, equal to the version):
   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. **Create the GitHub release** for that tag (via the GitHub UI or
   `gh release create vX.Y.Z`). No archive needs attaching - the tag/ref is the
   artifact.

Cutting the tag and publishing the release are deliberately **operator
actions**: the agent prepares and verifies, the human releases.

## Pinning a release (adopter)

Install goes through the plugin marketplace:

```
/plugin marketplace add neilgfoster/lume
/plugin install lume@lume
```

The version you get is whatever is in `plugin.json` at the ref the marketplace
resolves. To pin a specific release reproducibly, point the marketplace at a
tagged ref of this repo rather than its default branch - the exact pin syntax
depends on your Claude Code version, so check `/plugin marketplace --help` (or
the Claude Code plugin docs) for how it accepts a git ref. The tag `vX.Y.Z`
always corresponds to `plugin.json` version `X.Y.Z` (enforced by
`tools/check_release_tag.py`), so the tag is an unambiguous pin target.
