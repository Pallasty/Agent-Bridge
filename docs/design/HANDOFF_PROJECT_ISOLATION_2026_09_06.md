# Project-isolated handoff brief

Status: source repair implemented and focused validation passed;
retained-capability defect repair only.
Base: `9df8ce701b6444e640169f5c47d4148cde48ae49` (GitLab and GitHub master).
Owner direction: implement the bounded outcome of the OpenHuman / VoiceMem
review, retaining the existing memory architecture.

Problem: `session_handoff(cwd)` binds Git state to cwd but selects todos and
handoffs from all projects, so unrelated records can occupy the recovery brief.
Retained local MCP telemetry (2026-05-03 through 2026-09-06): zero recorded
calls to this tool; natural harmful-recall occurrences are not established.
Owner cost: unmeasured; do not infer saved time from regression fixtures.
Read-only retained-data projection: the old default selection for the Mac AB
project returned 20/20 todos and 10/10 handoffs from other scopes, despite 5
active exact-project todos and 6 active exact-project handoffs being present.
This replays selection SQL, not an observed owner invocation or benefit trial.
Smallest closure: the retained handoff tool returns only current project rows,
using existing bootstrap handoff eligibility, with bounded reads.
Increment: one source repair, focused tests and an independently reviewed diff;
no deployment, profile expansion, new memory mechanism or model runtime.
Doing nothing: the unused local tool retains a reproducible cross-project
selection defect; the ordinary Codex bootstrap remains on its existing path.

## Contract

- Preserve existing output fields, optional narrative fields, Git snapshot,
  todo importance ordering, handoff creation ordering and caller output caps.
- Read candidates with the existing scoped Store API; exact project equality
  is then checked independently, because Store visibility also includes global
  and ancestor records. Match trailing slashes like the bootstrap gate.
  The coarse Store lookup uses the raw directory with a trailing slash so it
  includes rows whose stored project scope ends with a slash; the final exact
  comparison still excludes ancestors, siblings and globals.
- Todos must be active, exact-project, not superseded and not explicitly stale.
  Handoffs additionally pass the existing bootstrap priority predicate. Reuse
  that predicate without changing bootstrap ranking or eligibility semantics.
- The current predicate excludes auto-curated, identifier-unverified, stale
  and background-only handoffs. It does not require every row to carry
  `confidence=verified`; this repair does not redefine that policy.
- Read at most 256 candidates per kind and apply eligibility before the caller's
  output cap. Expose candidate-limit flags so a bounded empty result cannot be
  mistaken for proof that no relevant memory exists. No unlimited scan or new
  Store query framework is introduced.
  The additive output field is `candidate_limit_reached` with `todos` and
  `session_handoffs` booleans; a true flag means possibly incomplete, including
  the conservative exact-256 case.
- Selection does not modify memory content, status, access counters or edges.
  Normal MCP dispatch telemetry remains outside this read-only helper.

## Validation and completion

Use temporary SQLite records and the actual helper: cross-project/global/
ancestor/sibling rows cannot enter either section; excluded newer rows cannot
consume a caller's one-row slot; stale, superseded and ineligible handoffs are
removed; eligible row ordering, limits, narratives and Git fields survive.
Exercise candidate-limit exhaustion and read-only behavior explicitly.
Run the existing bootstrap eligibility/digest and tool-profile regressions.
An independent source review checks scope, bounds and compatibility.

Completed on 2026-09-06:

| Check | Result |
| --- | --- |
| Old helper with regression fixtures | 1 passed, 4 failed: wrong-project selection, stale/replaced selection, unbounded selection and missing completeness flags reproduced |
| Repaired `session_handoff::tests` | 5 passed, 0 failed |
| Existing `bootstrap_handoff_priority_tests` | 3 passed, 0 failed |
| Existing `session_bootstrap_state_digest_keeps_only_priority_eligible_handoff` | 1 passed, 0 failed |
| Existing `cold_standard_tools_demoted_to_niche` | 1 passed, 0 failed |
| Repository pre-commit `cargo check -p ab-bridge --all-targets --quiet` | Passed with default features; compiler warnings remain |
| Independent final source review | No blocking findings; scope, bounds, compatibility and fixture validity checked |
| Whitespace and formatting | `git diff --check` and handoff-file rustfmt passed; the large `mcp_tools.rs` retains exactly the base's 258 formatting hunks, with no new formatting debt |

The four new tests use temporary SQLite databases and the actual helper.
They also compare complete memory records and relationship edges before and
after selection. No production memory mutation or live MCP invocation was
performed. This is a source regression result, not a full-feature build,
deployment, end-to-end voice result or measured owner benefit.

Reproduction command (from this worktree):

```sh
RUSTC=/Users/pallasting/.rustup/toolchains/1.96.1-aarch64-apple-darwin/bin/rustc \
RUSTDOC=/Users/pallasting/.rustup/toolchains/1.96.1-aarch64-apple-darwin/bin/rustdoc \
CARGO_TARGET_DIR=/Users/pallasting/Projects/agent-bridge/target \
/Users/pallasting/.rustup/toolchains/1.96.0-aarch64-apple-darwin/bin/cargo \
  test --locked -p ab-bridge --no-default-features --lib \
  session_handoff::tests -- --test-threads=1
```

The repository-pinned Rust 1.96.1 compiler was used; that local installation
lacks Cargo/rustfmt, so the installed 1.96.0 Cargo/rustfmt supplied those
frontends without changing the toolchain configuration. The three adjacent
test filters ran from the same newly built test binary. They used
`TMPDIR=/private/tmp` because existing fixtures otherwise encounter macOS's
`/var` symlink under SQLite's no-follow policy. New fixtures canonicalize their
temporary database directory and pass with the default temporary directory.
Initial fixture compilation/path failures were resolved before recording the
behavioral failing baseline; they are not counted as product regressions.
The pre-commit check used the same compiler and target directory, with the
installed Cargo directory prepended to `PATH`; no hook bypass was used.

Source completion means the regression is reproduced and repaired on the
pinned candidate, focused checks pass and the implementation is locally
committed and reviewable. It does not populate the independently verified
no-restatement north-star numerator or prove user benefit. Natural use and
deployment remain separate decisions; this defect repair does not reopen R1
sampling or create another experimental lane.

Rollback: revert this task's isolated commit; no persistent data migration.

## MCP entry acceptance and source integration

The 2026-09-06 continuation closes the existing repair's delivery path. It does
not start another memory experiment. Both remote master refs were reread at
the original base before integration; the repair is commit
`74841b6084b3286aaa0954d3249a417f277d752f`.

A newly compiled, ONNX-free debug binary reported `74841b6084b3` and SHA-256
`b276e00582f36b5326933893db8fcf0dfeb81f4a3ac3dfc31e010db042a7bdd1`.
One real `agent-bridge mcp` process passed JSONL initialize and one
`session_handoff` call against 22 synthetic SQLite rows. Higher-ranked global,
ancestor, lexical-prefix sibling, unrelated, stale, superseded, replaced,
auto-curated and identifier-unverified records did not displace the current
project's eligible records under one-row output limits. Git state, narrative
fields and the additive candidate-limit flags survived MCP serialization.
The memory/edge row snapshots were unchanged, telemetry contained exactly one
`session_handoff` call, the process exited zero and its process group was absent.

The probe used a fresh environment allowlist, hash embeddings, PTY backend and
explicit temporary DB, state, receipt spool, browser and XDG directories. It
did not inherit production credentials or remote embedding settings, change
HOME, or invoke memory-write tools. Startup initialization and dispatch
telemetry wrote only to the selected temporary state. This establishes the
real MCP entry with isolated fixtures, not the installed ordinary profile or
a naturally resumed task.

Source integration follows the existing GitHub PR and normal CI workflow,
then a non-force fast-forward of the same merge commit to GitLab with both
remote refs read back. Runtime deployment and tool-profile expansion are
excluded: the current ordinary profile does not expose this niche tool, and
the retained telemetry has no natural call to justify replacing the runtime.
Future use should record only an actual missing, stale or harmful recall
regression; successful fixtures do not reopen routine positive sampling.
