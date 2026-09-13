# S16 Avatar presentation boundaries and S17 capability evaluation

## Preregistered scope

Source: `c4162953` (fetched GitHub master), 22,827 lines in main.rs.
The accepted S14 inventory lists nine additions but its S16 prose says eight.
Current source has a tenth addition, FocusFollowObserve. This unit covers all
ten: SpriteAssetAudit, SpriteAssetCompile, SpriteAssetContract, FocusFollowPlan,
FocusFollowRecommend, FocusFollowPrompt, FocusFollowAction, FocusFollowObserve,
LinuxLive, VoiceObserve. It preserves the original 43-command S7 boundary.

Acceptance: exact baseline/candidate CLI help, successful text/JSON and failure
output parity on deterministic isolated fixtures; frozen plan/result tests for
live-only outputs; ownership and effect-order checks; four S15 ownership tests
and timer tests; cargo check -p ab-bridge --all-targets --quiet; staged and
committed governance admission; diff/format checks. No live desktop or audio
execution is needed to accept behavior-preserving presentation movement.

## Ownership decisions

| Commands | Eligible seam | Retained at root |
| --- | --- | --- |
| SpriteAssetAudit | completed typed report rendering | path acquisition, audit invocation, render-before-rejection ordering |
| SpriteAssetCompile | completed typed report rendering | execute/confirm check, read/write invocation |
| SpriteAssetContract | completed typed contract rendering | asset root and filesystem aggregation invocation |
| FocusFollowPlan | completed plan rendering | Sway acquisition and options injection; planner already domain-owned |
| FocusFollowRecommend | completed recommendation rendering | Sway and acknowledgement acquisition; recommendation already domain-owned |
| FocusFollowPrompt | completed prompt rendering | clock/cooldown receipt acquisition, preflight invocation, show/confirm, notification/native state, receipt writes and JSON-only early failure |
| FocusFollowAction | completed action rendering | authorization, cancel/lock/timeouts, per-step gate and move ordering |
| FocusFollowObserve | completed receipt rendering and pure context projection | lock, pause file, polling, receipt writes, pre-action safety gate and execution |
| LinuxLive | immutable plan and completed receipt projection/rendering | sidecar/environment acquisition, configuration validation, Presence store, timers/task spawn/join and final sync |
| VoiceObserve | immutable plan and completed receipt projection/rendering | sidecar/environment acquisition, adapter readiness check, voice loop and elapsed clock |

No helper receives a Store, Hub, executable runner, filesystem reader or clock.
Rendering may serialize and print exactly where the root previously printed.
Typed domain reports remain typed. Existing JSON contracts remain JSON; this
slice does not rename fields or impose a new public schema.

The observer's action gate and target-geometry constraint comparison remain an
explicit root exception: these pure predicates are coupled to the per-step
identity/fullscreen/sensitivity/travel safety ladder and root-local constraint
types. Moving them without a dedicated authority contract would obscure the
ordering this ADR must preserve. Only observation context projection moves.

## S17 decision criteria

Inspect real consumers after S16. A shared live-execution capability requires
a second consumer or a stable authority interface plus deterministic parity.
Do not build a generic scheduler or move the whole Avatar family to cli::avatar.
Record the consumer search, evidence and resulting decision at closeout.

## Continuous admission repair

A receipt must bind its exact source commit and before/after file digests.
Comparison-base commits with identical main.rs content are equivalent; a
multi-commit diff may use a connected sequence of valid receipts. Missing
intermediate transitions and unrelated history must fail. Pre-commit validates
the staged tree even when CI is skipped. Historical missing receipts remain
historical gaps; a current audit must not claim they passed at their original
commit time.

## Rollback

Revert this extraction to restore inline projections; no environment, state,
authority or deployment rollback is required. Revert admission changes
separately if needed; preserve the historical audit record.

## Post-S15 current-state audit

The main.rs delta from S15 merge `588fac65` to this source base is +552/-11
(541 net lines). The first-parent history contains ten changes touching the
file. They fall into these regions:

- Resident schema, value-enum conversions and cross-domain dispatch: CLI
  schema/routing. The root retains typed options and the credential-load
  boundary. Domain modules already own cognition, risk policy, owner labels,
  M2 evaluation and review. The few JSON print calls are direct result adapters,
  with no local aggregation or business logic.
- Resident preflight and option/store construction: authority/effect adapters
  and dependency injection. Risk admission stays before SQLite/journal access;
  Resident dispatch stays before general credential loading.
- Internal workload supervisor entry: process startup. It stays before SIGPIPE
  restoration to preserve parent-loss EOF/EPIPE behavior.
- R9 workload-receipt reconciliation in build_hub: dependency/startup custody.
  The default-off feature and store-open/scan/backend-construction order remain.
- R9 reconciliation summary: pure report formatting. This audit extracts it to
  cli::startup_report with the same feature gate, filter and tracing fields.
- daemon-http help/default/listen log: CLI contract and explicit listener
  authority. The local default and environment override remain root-visible.
- Added startup trace and Resident parser tests: acceptance evidence, not runtime
  responsibilities. Existing tests are retained.

The S15 published receipt updated the after hash during `01317deb` but retained
source `77600c91` instead of merge-parent `209514a7`. That was not just a
commit-ID mismatch: the source blobs also differ. The originally published
receipt remains rightly red when replayed from that historical merge. Later main.rs commits supplied no new receipts.
This work does not rewrite their history or claim historical CI success. The
current S15 receipt is corrected to its actual merge-parent source; a
separate retrospective receipt binds S15 to c4162953, and the S16 receipt binds
c4162953 to the extraction. The four S15 modules and ownership tests are
byte-identical from the merge to the audited baseline, so current timer and
boundary tests also cover that retained implementation. The gate accepts a
retrospective prefix only when it ends at the actual comparison base; it still
requires full forward coverage for a new main.rs change.

## S17 evaluation outcome

Retain the existing root-owned execution adapters; no new capability interface.
Source search finds run_avatar_linux_live and run_avatar_voice_observe each
called by their CLI dispatch only. execute_avatar_focus_follow_action has two
call sites (explicit action and bounded observer), both inside the same process
composition root. These are real reuse, but not two independently owned
capability consumers: both depend on root-local lock, deadline, compositor
identity, target-geometry and per-step cancellation constraints.

S16 establishes tested immutable view interfaces without transferring those
capabilities. A new trait/module wrapping the entire live executor would hide
this authority ladder while adding no independent consumer. The S17 evaluation
is complete with a retain decision; implementing a speculative capability is
not an acceptance requirement. Reopen only for an actual new consumer or a
separately characterized stable authority interface.

## Verification artifacts

- `docs/reports/main-rs-governance/2026-09-13-verification.json` records binary
  hashes, 82 exact CLI/effect comparisons, source hashes and successful test runs.
- Twenty real Git/hook tests exercise exact content/ancestry, staged isolation,
  multi-commit chains and retrospective repair, including uncovered-change
  negative controls. The wrapper gate runs these plus its 3 positive/7 negative
  schema checks before repository admission.
- The tracked pre-commit hook is installed in this clone. CI remains explicitly
  skipped under AGENTS.md. No deployment or live desktop/audio acceptance is
  claimed.
- The retained main.rs has 22,472 lines (355 fewer); no line budget is imposed.
  This finishes the accepted S14–S17 campaign. Future feature changes remain
  subject to continuous classification and contract evidence.
