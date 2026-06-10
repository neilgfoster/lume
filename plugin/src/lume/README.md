# Lume engine

Deterministic control layer for the iteration loop. No inference or network I/O
in this code - it reads, parses, and writes on-disk workstream state. Inference
is reserved for the work an iteration contains, never the mechanism.

## Layout
The plugin root is `plugin/`; the engine lives under it in a `src/` layout. The
operator's state lives in a separate `.lume/` directory that this code locates
by walking up from the cwd (it is created in the operator's own repo, never
shipped with the plugin).
```
plugin/                # the plugin root
  bin/lume             # executable entry point (on PATH when installed)
  src/lume/            # package
    frontmatter.py     # parse/render the --- key: value --- block
    clock.py           # Clock seam (SystemClock / FixedClock) - injected for testability
    iteration.py       # Iteration model + phase rules
    workstream.py      # Workstream model + the open-iteration gate
    repository.py      # locate .lume/, resolve the workstream (tracking seam)
    validate.py        # schema validation; schemas/ holds the JSON Schemas
    migrate.py         # one-shot state migrations
    seed.py            # the seed (id 0) bootstrap workstream
    cli/               # command dispatch + error->exit-code mapping

.lume/                 # operator state, in the operator's repo (NOT shipped)
  workstreams/
    NNNN-<slug>/       # objective.json, state.json, decisions.json, iterations/NNNN-<slug>.json
```
The test suite and `conftest.py` live at the development repo root, outside
`plugin/`, so they are not part of the installed plugin.

## Run the CLI (from anywhere inside a project that has a `.lume/`)
```
lume status            # re-orientation: objective + current phase + Done/Now/Next
lume open "<title>"    # open the next iteration (refused unless the latest is accepted)
```

## Run the tests (from the repo root)
```
python3 -m pytest                                                 # conftest.py puts plugin/src on the path
PYTHONPATH=plugin/src python3 -m unittest discover -s tests -t .   # stdlib runner
```

## Design notes
- Dependency injection (constructor injection, not a container): the `Clock` and
  the filesystem start path are injected into `Repository`/`Workstream`, so logic
  is testable without the real repo or the real wall-clock.
- `repository.py` is the documented tracking/persistence seam (local files today;
  a GitHub Issues / Jira backing later). Kept concrete until a second
  implementation pulls on it - per [scope.md](../../../docs/scope.md), don't over-abstract early.

---
Part of the lume docs: [user guide](../../README.md) · [project README](../../../README.md) · [design records](../../../docs/scope.md).
