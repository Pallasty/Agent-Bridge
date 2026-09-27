# Jev browser validation and adoption decisions

Date: 2026-09-27. User direction: plan the Jev validation goals, validate them,
and implement feasible outcomes. The initial plan was committed as `c970b138`.

Base: canonical `Pallasty/Agent-Bridge main` at
`6c4b1a9f332d8b9e9329f8d2914deed7db713453`; branch
`codex/jev-browser-validation-20260927`. Implementation: `af12defe56aa93f5cbb7c6257e7e9d0229a70030`;
tested tree: `e689c15976db89e7c8aca3d4c680cb6589c08485`. The later evidence commit is not the tested
implementation tree.

| Goal | Acceptance | Result |
| --- | --- | --- |
| P0: reference binding | Reproduce reuse of an expired ref, reject it without input, preserve valid trusted clicks, test clone/page allocation and exhaustion. | PASS: fix implemented without changing the MCP ref grammar or backend trait. |
| P1: observation comparison | Compare existing AX and unchanged pinned DOM reader; preserve required target coverage before considering adoption. | HOLD_DIRECT_DOM_REPLACEMENT: DOM misses two shadow-root targets present in AX. |
| P2: model selection | Fixed model and representative paired tasks, complete outcome oracle, abstention/fallback, full cost accounting. | NOT_RUN for real inference and task value; no provider integrated. |

## P0: demonstrated defect and narrow repair

The original code restarted `@eN` allocation for every snapshot. The RED unit
regression resolved an old Save ref to the new Delete node. In an isolated real
Chrome test, all five stale or wrong-page ref calls returned success and each dispatched
one trusted click when no input was expected. After the repair, all five calls
are rejected and dispatch zero clicks. Six positive controls each dispatch one
correct trusted click. These are checks within one E2E, not eleven independent
tasks or observed user incidents.

The five negative cases cover replacement plus snapshot, same-node re-snapshot,
reload plus snapshot, cross-page misuse, and a snapshot through a backend clone.
Positive controls also preserve another page's valid ref across this page's
refresh. Unit coverage includes concurrent allocation and counter exhaustion.
The existing real-Chrome click-by-ref E2E also passes.

The compatible implementation uses a checked `AtomicU64` shared by one backend
and its clones, across all its pages. It never resets on snapshot, page close,
or browser handle replacement. Only a successfully built tree replaces the
page's ref map. Old refs become unknown; exhaustion errors without wraparound
or partial publication. The MCP grammar remains `@e<digits>`; schema changes
are explanatory descriptions only.

The contract is the latest **successfully published map**, not request start
order or proof of the newest DOM. Uniqueness does not extend across independent
backend instances or process restarts. A failed snapshot retains the earlier
map. The fix neither cancels an action whose lookup already copied the backend
node ID nor makes lookup, validation and input atomic. Semantic changes without
a new snapshot, focus, geometry and occlusion races remain outside this fix.
Snapshots containing interactive refs can have different output hashes despite
unchanged DOM: the existing hash includes refs and is not a normalized DOM hash.

## P1: measured coverage, bounded timing

Upstream is pinned to [`1231850a`](https://github.com/browser-use/jev-ultrafast/tree/1231850a0bf1a0c0341fe408ef1668dbbfdfac46).
The harness checks the exact loaded `snapshot.js` bytes against SHA-256
`e50473501c8fb8e70f3b21866d987393e3f2315c639d638bd477d170e81ed78d`
before evaluating the unchanged source. No upstream Python package or model is
installed. Chrome version: `154.0.8037.57`.

Four controlled data pages, one warmup per method/page, fifteen alternating
pairs per page, and a fixed 1120x780 viewport produced 120 successful final-run
observations. Targets are scored by returned role/name records; text, marker
and guard strings do not count as target recall. Every repeated observation
had the same target-coverage result.

| Fixture | AX targets | DOM targets | AX p50 | DOM p50 | AX p95/max | DOM p95/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ordinary_html | 3/3 | 3/3 | 7.757 | 6.226 | 51.310 | 20.356 |
| checkbox_and_native_select | 2/2 | 2/2 | 7.342 | 6.272 | 8.012 | 7.314 |
| open_shadow_root | 3/3 | 1/3 | 7.673 | 5.960 | 23.227 | 8.483 |
| same_origin_srcdoc_iframe | 1/3 | 1/3 | 4.167 | 4.675 | 7.051 | 7.060 |

Times are milliseconds around one backend observation, including transport and
AX projection. Post-call JSON serialization, coverage scoring and logging are
excluded. At n=15, nearest-rank p95 equals the maximum; the raw data retains
it but does not establish stable tail latency. Run 1 and the final rerun differ
in timing, and unrelated Cargo compilation overlapped these measurements.
This is not evidence of a controlled performance improvement, full-task speed
or total cost. CDP call counts were not instrumented. The current AX path already
uses one `GetFullAxTree` plus local conversion, so upstream protocol-call savings
cannot be transferred to Agent-Bridge.

The current `A11yNode` projection lacks checked-state even though both methods
recall the checkbox; DOM retains `checked=true`. This is a projection gap, not
evidence that the raw AX protocol lacks checked-state. Native-select recall is
control recall, not proof of option completeness or equivalent input behavior.
Both current entrypoints miss iframe targets; that gap is shared. DOM alone
misses the shadow-root button and textbox present in AX. Direct replacement
therefore fails acceptance. Neither a hybrid fallback nor action equivalence
was tested. These findings do not automatically authorize a wider browser rewrite.

## P2: retained evaluation design

The earlier offline AST probe again met 14/14 expectations with explicit
transport/prompt doubles. Some expectations demonstrate limitations: confidence
zero still reaches selection, and the Flights checker accepts synthetic wrong
passenger/cabin values that it does not examine. This is not fourteen successful
tasks or measured model quality. The previous research and complete pinned
source snapshot remain in `/Data/session-archives/20260927-jev-ultrafast-research/`.

A future natural-task evaluation should freeze the model version, task set,
candidate observations and budgets; compare existing selection with constrained
operation/target selection in paired runs; score every requested outcome using
an independent oracle; and retain all failures, retries, abstentions and fallback
calls. Calibrate confidence thresholds on separate data. Count selection,
text generation, transport, browser and fallback costs. Reopen adoption only
after repeated task benefit with preserved correctness and complete costs.
Real provider inference, model quality, natural-task success and cost remain
NOT_RUN in this delivery.

## Verification, evidence and delivery boundary

The unbypassed normal pre-commit passed: 24 Rust boundary tests, 405 pure
behavior cases, 143 fresh isolated CLI comparisons and
`cargo check -p ab-bridge --all-targets --quiet`. The CLI governance comparison
uses its own pinned baseline `4287aee34b2286ffe38c08316f1b52f1d755bc75`, distinct
from this change's release base and the P0 RED baseline. Its portable bundle
was independently checked against the implementation commit and relocated
for read-only verification; this is integrity checking, not another CLI run.

Browser checks: 8 unit tests, the new real-Chrome regression, the existing
click-by-ref E2E, final observation probe, and package formatting pass. Normal
Clippy exits 0 after fixing the new probe lint. Strict Clippy exits 101 because
of seven findings traced to unchanged baseline code/layout. The baseline
comparison is source inspection, not execution of baseline Clippy; this report
does not claim a warning-free build.

Evidence is in [the adjacent bundle](2026-09-27-jev-browser-validation/).
`validation-binding.json` and both source-hash files explain the sole post-package
change: equivalent parity arithmetic in the observation harness, followed by its
own formatting, Clippy and real-browser rerun. Production and P0 test bytes did
not change. Raw final observations, RED/GREEN logs, cleanup receipts and the
normal-gate CLI bundle are retained. Hash binding checks identity and internal
integrity; it is not independent authentication of the experiment author.

Builds used real disk. Browser profiles were unique, and final exact-profile
process scans and path checks found no test-browser residue. The initial RED
teardown race was fixed, and its residual owned profile was separately verified
and removed. An initial build-lock wait was cancelled only for this task's
waiting Cargo process; the unrelated holder was preserved. Existing dirty
worktrees, shared caches and the installed runtime were left in place.

Delivery is an explicit review branch with `[skip ci]` and GitLab `ci.skip`,
followed by remote-ref readback. No mainline merge, installed artifact update,
runtime enablement, service verification or client reconnect is claimed.
Source rollback is a normal revert of the implementation commit; there is no
runtime configuration change to undo.

To review the portable CLI evidence:

```sh
python3 scripts/eval/cli_governance_bundle.py \
  --run-dir docs/reports/goal-c-u/2026-09-27-jev-browser-validation/cli-bundle \
  --candidate-commit af12defe56aa93f5cbb7c6257e7e9d0229a70030
```

To rerun the browser regression, use an installed Chrome and a real-disk Cargo
target, then run `cargo test -p ab-browser --test observation_ref_e2e -- --ignored --nocapture`.
The observation harness header documents its separate opt-in environment; its
pinned script and license are included in the evidence bundle. Use a new profile
and new output path, and verify owned-browser/profile cleanup after the run.
