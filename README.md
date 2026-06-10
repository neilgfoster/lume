# lume (development repo)

A deterministic, operator-driven iteration loop, packaged as a Claude Code
plugin. **The machine does not act without the operator.**

> Using lume? The installable plugin and its full docs live in
> [`plugin/`](plugin/README.md). Install with:
> ```
> /plugin marketplace add neilgfoster/lume
> /plugin install lume@lume
> ```

This repository is where lume is developed (and where it dogfoods itself). It is
laid out so that only the plugin ships to adopters:

```
plugin/                  # the installable plugin (this is what gets installed)
  .claude-plugin/plugin.json
  bin/lume               # entry point (on PATH when installed)
  src/lume/              # the engine (stdlib-only Python package)
  skills/lume/           # the guiding skill
  README.md              # front-door docs for adopters
.claude-plugin/
  marketplace.json       # marketplace entry; source -> ./plugin
tests/                   # the test suite + conftest.py (dev only, not shipped)
docs/                    # design notes (dev only)
.lume/                   # lume's OWN workstream state (dev only, not shipped)
```

The marketplace points its plugin `source` at `./plugin`, so installing lume
brings only `plugin/` - `.lume/`, `tests/`, and `docs/` stay out of an adopter's
plugin cache.

## Develop / test

```
python3 -m pytest                                                 # conftest puts plugin/src on the path
PYTHONPATH=plugin/src python3 -m unittest discover -s tests -t .   # stdlib runner
```

Drive lume in this repo via the bundled entry point:

```
plugin/bin/lume status
```

See [`plugin/README.md`](plugin/README.md) for the user-facing guide and
`plugin/src/lume/README.md` for engine internals.
