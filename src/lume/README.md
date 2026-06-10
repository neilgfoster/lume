# Lume engine

Deterministic control layer for the iteration loop. No inference or network I/O
in this code - it reads, parses, and writes on-disk workstream state. Inference
is reserved for the work an iteration contains, never the mechanism.

## Layout
The engine lives in the repo (and plugin) root under a `src/` layout; the
operator's state lives in a separate `.lume/` directory that this code locates
by walking up from the cwd.
```
bin/lume             # executable entry point (on PATH when installed as a plugin)
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
tests/               # stdlib unittest
conftest.py          # puts src/ on sys.path for the test run

.lume/               # operator state (NOT part of the plugin package)
  workstreams/
    NNNN-<slug>/     # objective.json, state.json, decisions.json, iterations/NNNN-<slug>.json
```

## Run the CLI (from anywhere inside a project that has a `.lume/`)
```
lume status            # re-orientation: objective + current phase + Done/Now/Next
lume open "<title>"    # open the next iteration (refused unless the latest is accepted)
```

## Run the tests (from the repo root)
```
python3 -m pytest                                          # conftest.py puts src/ on the path
PYTHONPATH=src python3 -m unittest discover -s tests -t .   # stdlib runner
```

## Design notes
- Dependency injection (constructor injection, not a container): the `Clock` and
  the filesystem start path are injected into `Repository`/`Workstream`, so logic
  is testable without the real repo or the real wall-clock.
- `repository.py` is the documented tracking/persistence seam (local files today;
  a GitHub Issues / Jira backing later). Kept concrete until a second
  implementation pulls on it - per scope.md, don't over-abstract early.
