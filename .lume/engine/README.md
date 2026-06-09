# Lume engine

Deterministic control layer for the iteration loop. No inference or network I/O
in this code - it reads, parses, and writes on-disk workstream state. Inference
is reserved for the work an iteration contains, never the mechanism.

## Layout
```
.lume/
  engine/
    lume/            # package
      frontmatter.py # parse/render the --- key: value --- block
      clock.py       # Clock seam (SystemClock / FixedClock) - injected for testability
      iteration.py   # Iteration model + phase rules
      workstream.py  # Workstream model + the open-iteration gate
      repository.py  # locate .lume/, resolve the workstream (tracking seam)
      cli.py         # command dispatch + error->exit-code mapping
    bin/lume         # executable entry point
    tests/           # stdlib unittest
  workstreams/
    <slug>/          # objective.md, snapshot.md, decisions.md, iterations/NNN.md
```

## Run the CLI (from the project root)
```
.lume/engine/bin/lume status          # re-orientation: objective + current phase + Done/Now/Next
.lume/engine/bin/lume open "<title>"   # open the next iteration (refused unless the latest is accepted)
```

## Run the tests
```
cd .lume/engine && python3 -m unittest discover -s tests -t .
```

## Design notes
- Dependency injection (constructor injection, not a container): the `Clock` and
  the filesystem start path are injected into `Repository`/`Workstream`, so logic
  is testable without the real repo or the real wall-clock.
- `repository.py` is the documented tracking/persistence seam (local files today;
  a GitHub Issues / Jira backing later). Kept concrete until a second
  implementation pulls on it - per scope.md, don't over-abstract early.
