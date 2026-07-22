# Code Review Graph Probe

This probe evaluates `code-review-graph` as an advisory comparison engine. It
is not an Agent-Bridge runtime dependency and does not install another MCP
server.

## Safety boundary

- The package version is pinned (`2.3.7` by default).
- `HOME` and `CRG_DATA_DIR` point at a temporary directory for every run.
- The script never calls `install`, `register`, `serve`, `daemon`, or
  `apply-refactor`.
- Graph data is deleted after the report is written unless `--keep-data` is
  explicitly supplied.
- Source files and the Git index are read-only inputs.

The package requires Python 3.10 or newer. The probe asks `uvx` for Python 3.13
by default (`CRG_PYTHON` overrides it) and keeps Python dependencies outside
the Agent-Bridge release.

## Run

```bash
scripts/eval/code-review-graph-probe.sh \
  --repo /path/to/repository \
  --base HEAD~1
```

Reports are written below `target/code-review-graph-eval/` and include:

- `manifest.txt`: pinned version, repository, commit, and isolation claims
- `build.log`: cold-build timing and parser output
- `status.json`: graph size and language inventory
- `detect-brief.txt`: bounded review summary
- `detect-full.json`: detailed advisory evidence
- `architecture.json`: minimal community/coupling view

Treat risk scores, test gaps, and token-savings estimates as advisory. Before a
CRG result affects an Agent-Bridge gate, compare it with source, tests, and the
native `codebase_*` graph. In particular, an inferred test gap is not proof
that a function lacks coverage.
