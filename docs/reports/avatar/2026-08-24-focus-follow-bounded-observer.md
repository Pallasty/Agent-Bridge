# Xiao Shu bounded Focus-follow observer candidate

Date: 2026-08-24

Status: **automated verification passed; merge, deployment, and live verdict pending**

## Decision boundary

This increment turns repeated manual recommendation checks into one bounded
owner-local observation session. The owner starts it once in the foreground;
inside that session, AB may express a qualifying focus transition by moving
only Xiao Shu. The move is AB's reversible presentation, so there is no
per-move confirmation prompt.

This is not an always-on feature. It is default-off, runs for at most 30
minutes, installs no service, has no autostart path, and creates no durable
observer-run history. Closing the foreground process, cancellation, the
duration bound, or the attempt budget ends the session.

The frozen defaults are:

- duration: 30 minutes;
- poll interval: 1,000 ms;
- stable-focus dwell: 2,000 ms;
- post-action cooldown: 300 seconds;
- failed-action backoff: 30 seconds initially, exponential, capped at 900
  seconds;
- move budget: three real attempts, including completed, cancelled, and failed
  attempts;
- default eligible travel: at least 96 px and no more than 900 px.

Duration and attempt-budget options may select smaller values, but normalization
cannot raise either above 30 minutes or three attempts.

The first focused window after startup establishes the session baseline. It
can never trigger movement. A later target must remain stable for the dwell
period and pass every policy gate before it can consume an attempt.

## Frozen policy gates

Dispatch is suppressed when any of the following is true:

- the candidate is the startup baseline, is unstable, is already acknowledged,
  or has already been attempted in this run;
- the session is in cooldown or failure backoff, or its three-attempt budget is
  exhausted;
- the focused target reports fullscreen;
- the focused target or an ancestor carries the exact `ab-sensitive` Sway mark;
- a structured exact app identity is absent;
- that exact app identity appears in the conservative built-in
  authentication/password-manager denylist or the owner-provided exact
  denylist; titles and substrings are never used to infer sensitive context;
- the owner-local pause signal is active;
- the Focus-follow action lock is unavailable;
- the focused target's exact rectangle, workspace rectangle, or workspace
  changes after dispatch;
- Xiao Shu's observed position diverges from the expected path, including an
  owner Super-drag during traversal;
- the planned travel is below the configured minimum (96 px by default), above
  the configured maximum (900 px by default), or the underlying exact
  Avatar/target plan fails closed.

The closed travel reasons are `below_min_travel` and `above_max_travel`. The
built-in case-sensitive exact denylist is:

- Wayland app ids: `com.1password.1password`, `com.bitwarden.desktop`,
  `org.keepassxc.KeePassXC`, and `org.gnome.seahorse.Application`;
- XWayland classes: `1Password`, `Bitwarden`, and `KeePassXC`.

Each repeated `--deny-app-id ID` adds that exact string to both structured
identity sets. Neither exact identity nor `ab-sensitive` handling performs a
title or substring classification.

A failed real action cannot create a poll-speed retry loop. It consumes one
attempt, suppresses the same target for the rest of the run, and advances the
bounded exponential failure backoff. Cancellation is likewise an attempted
outcome, not permission to retry immediately. Observation-read failures advance
the same backoff without movement or attempt consumption; three consecutive
tree-read failures terminate the run as a runtime failure.

A runtime failure that is proven to occur before a durable action start is
counted separately as `prestart_runtime_failed`; it neither consumes an attempt
nor increments `tree_read_failure_count`. This keeps action, sensor, and runtime
learning evidence distinct while retaining bounded backoff and fatal-stop
behavior.

## Effect and privacy ceiling

The observer may invoke only the existing exact-Avatar Focus-follow action.
It does not show a prompt or bubble, emit audio, follow or move the pointer,
change keyboard focus, inject input, operate the focused application, inspect
its content, or mutate user data. Fullscreen and app identity are structured
policy inputs only. There is no title-based sensitive-content classifier and
no claim of generic quiet/DND, meeting, game, or screen-sharing detection.

Before movement can occur, the observer atomically writes one bounded
`status=running` safe projection to the owner-runtime receipt file. On a handled
terminal path it atomically replaces that file with the final aggregate and
also prints the final projection to stdout. The projection contains only
terminal status, elapsed time, aggregate counters, structured suppression
reasons (including `above_max_travel`), frozen bounds, and the zero-input
effect/privacy contract. It must not contain window titles, app ids, raw Sway
tree data, paths, prompt content, or free-form reason text. The runtime receipt
is not a second durable action log; an unreplaced `running` receipt is evidence
of an interrupted run, not a successful terminal outcome.

Every real movement continues to write the existing durable Focus-follow
outcome v2 `started`/`final` pair under
`<state_root>/avatar-focus-follow/outcomes.jsonl`. The shared `attempt_id`,
postcondition verification, and positive/negative outcome remain the durable
truth for the action. A final observer aggregate cannot upgrade a missing or
failed v2 terminal record into success.

## Candidate operation

Inspect the frozen plan without starting a polling session or moving Xiao Shu:

```bash
agent-bridge avatar focus-follow-observe --json
```

Start one bounded foreground session explicitly:

```bash
agent-bridge avatar focus-follow-observe --execute --json
```

There is no `--confirm` flag and no caller-supplied free-form reason. Omitting
`--execute` returns the preflight immediately. Repeating `--deny-app-id ID`
adds owner-local exact app identities. The pause path defaults to
`$XDG_RUNTIME_DIR/ab-focus-follow-observer.pause` and may be overridden with
`--pause-file PATH`; its presence suppresses dispatch and cancels an action in
progress. The final safe receipt defaults to
`$XDG_RUNTIME_DIR/ab-focus-follow-observer-receipt.json`. These commands
describe the candidate interface. Observer and action locks share the same
owner-private `XDG_RUNTIME_DIR`, so changing a durable state-root environment
cannot bypass exclusivity. Sway reads, movement, and animation sleeps share the
session's absolute deadline; after that deadline no new move can be issued.
Deployment and live use remain blocked until the source and installed binary
have been reconciled by the verification owner.

## Verification results — automated candidate PASS; live pending

No live or owner-observed result is asserted by this report yet. Fill this
section only with command output or direct owner-local observation from the
merged/deployed candidate; do not convert a source-only or unit-test PASS into
a live verdict.

| Check | Required evidence | Current result |
| --- | --- | --- |
| Parse/help and dry-run | command is default-off; dry-run exits without polling or movement | **PASS (automated)** |
| Duration and foreground lifecycle | one owner-started process exits by cancellation, attempt budget, or no later than 30 minutes | **PASS (1 s paused CLI); live pending** |
| Startup baseline | first focused target never dispatches | **PASS (policy + paused CLI)** |
| Dwell/debounce | focus churn resets dwell; only a stable later target is eligible | **PASS (policy)** |
| ACK and repeat suppression | compositor/Avatar-bound ACK v2, baseline, and already-attempted targets do not dispatch; stale/v1 ACK cannot suppress a new session | **PASS (automated)** |
| Fullscreen policy | structured fullscreen target is suppressed | **PASS (planner + locked gate)** |
| Identity and denylist policy | missing app identity, exact `ab-sensitive` mark, built-in exact identity, and owner exact identity suppress; title/substrings do not classify | **PASS (automated)** |
| Pause and action lock | active pause or unavailable lock yields no action | **PASS (CLI + lock tests)** |
| Bounds, geometry, and budget | travel bounds, stable target/workspace geometry, owner-drag cancellation, duration ceiling, and three-attempt ceiling are enforced | **PASS (automated)** |
| Failure behavior | action, observation, and prestart-runtime failures remain distinct; failed/cancelled targets do not retry; backoff is bounded | **PASS (automated)** |
| Action journal | every real attempt has the expected outcome v2 started/final evidence or an observable unmatched start | **PASS (automated); live matching pending** |
| Receipt privacy | initial `running` file is terminally replaced; stdout/runtime aggregate excludes title, app id, raw tree, paths, and free-form text | **PASS (automated)** |
| Authority ceiling | zero prompt/audio/pointer/focus/input/app-operation effects | **PASS (automated); live observation pending** |
| Owner value verdict | owner labels the session helpful, neutral, or distracting | **PENDING** |

Record later evidence here:

- source implementation commit: `f1031046`;
- installed binary commit/currentness: **PENDING**;
- focused automated tests: `cargo check -p ab-bridge --bin agent-bridge`
  plus 14 policy, 16 planner/ACK, 3 CLI lifecycle, 9 action lock/journal,
  2 locked observer/drag, and 1 ACK-cooldown tests — **45 passed, 0 failed**;
- independent adversarial static review: **PASS; no remaining high/medium finding**;
- dry-run receipt reference: **PENDING**;
- bounded live receipt reference: **PENDING**;
- matching outcome v2 attempt ids: **PENDING**;
- owner observation and value verdict: **PENDING**.

## Promotion and rollback rule

Promote this candidate only after a real desktop run establishes all policy
gates, zero pointer/focus/input interference, complete privacy-minimal receipts,
and practical owner value. Until then, the accepted baseline remains explicit
one-shot `focus-follow-action` execution.

Rollback is immediate: stop the foreground observer and do not start another
session. The ephemeral final receipt may be retained as bounded run evidence;
there is no daemon, scheduled job, observer-run journal, permission change, or
application state to clean up. If this second increment does not produce
daily-use value, refreeze R4-A rather than widening the observer.
