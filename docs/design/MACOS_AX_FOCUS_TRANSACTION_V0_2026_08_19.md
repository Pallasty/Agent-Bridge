# macOS AX Focus Transaction v0

## Outcome

`macos_ax_focus_transaction` is Agent-Bridge's first real rank-1 macOS semantic
actuator. It focuses one exact window and returns a closed-loop receipt:

```text
exclusive body lease
  -> durable pre-dispatch write-ahead marker
  -> live semantic precondition
  -> owner-standing rank-1 admission
  -> one bounded AX focus operation
  -> executor semantic postcondition
  -> independent hardened macos_ax_verify
  -> action receipt and embodiment-event record
```

Screenshots, OCR, coordinates, text entry, arbitrary AppleScript/JXA, and
model-written code are absent from this path.

## Exact target

The MCP surface requires:

- positive process ID;
- exact bundle ID; and
- a non-empty, sample-unique AXIdentifier.

An optional exact title can corroborate the stable identifier; the exact role
defaults to `AXWindow` and may be overridden explicitly. Window indices are
deliberately excluded from the real MCP action because they are sample-local.

The build-embedded Swift source performs another live AX enumeration in the
same process immediately before mutation and requires the unique match to be
the same CF element seen by the initial sample. Zero matches, multiple matches,
element replacement, or any window whose required selector attributes are
unreadable and therefore could hide another match block the action. The wrapper
verifies the deployed asset's bytes against the embedded source, then feeds the
embedded bytes over stdin to a pinned Apple Swift invocation. It resolves the
active developer directory with sanitized `/usr/bin/xcode-select`, resolves the
real invocation with sanitized `/usr/bin/xcrun --no-cache`, requires a root-owned
non-writable Mach-O inside that developer directory, verifies its Apple signing
identifier, and binds both the invocation path and canonical executable hash.
It never resolves an interpreter through caller-controlled `PATH`.

## v0 foreground boundary

v0 only focuses a window inside the application that is already frontmost. It
does not activate or switch applications. This gives the first mutation slice a
useful but tightly falsifiable boundary:

- a concurrent foreground change blocks or invalidates the transaction;
- a successful focus intentionally remains focused;
- no foreground restoration is needed because the executor never caused an
  application switch; and
- a user-created foreground change is never overwritten by compensation.

Cross-app activation is a later rank-1 transaction with a separate foreground
ownership and compensation design.

## Action primitive and verification

The executor prefers the application's writable `AXFocusedWindow` attribute.
If that attribute is explicitly unsupported, it may use the target window's
writable `AXMain` attribute as a recorded fallback. It then polls for at most
two seconds and requires all of the following:

- the foreground PID and bundle remain unchanged;
- the target AX element is still the unique exact match; and
- the application's focused-window attribute resolves to that same element.

An already-focused target is a verified idempotent no-op, not a fabricated
mutation.

The executor's own postcondition is necessary but not sufficient for a green
transaction. After the executor reports `verified`, the Rust wrapper invokes
the existing hardened `macos_ax_verify(window_focused)` path with the exact
bundle ID, PID, and AXIdentifier. That read-only verifier independently checks
its echoed request, process scope, proof coverage, source exit code, and
semantic envelope. The verifier and its sibling probe are materialized from
build-embedded bytes in a private temporary directory, run with fixed
Apple-signed Python from the same pinned developer directory under an
environment-cleared, bytecode-free invocation and a system-only `PATH`, and
removed after the transaction. Executor and verifier each run in an isolated
process group; timeout cleanup kills the full group and explicitly waits for
the leader before the body action lock can be released. A green result
additionally requires one exact matching window, complete and untruncated
enumeration, consistent counts, zero unknowns, and a focused witness. The
verifier reports `selector_candidate_count` separately from its focused-witness
list, so one focused window cannot hide a second unfocused window with the same
AXIdentifier. Unknown required selector attributes are also exposed and cannot
be used as evidence of uniqueness.

A complete readback that definitively observes the postcondition as unmet is
`not_verified`. A verifier error, missing receipt, malformed evidence, duplicate
target, or incomplete/truncated coverage is `outcome_unknown`: the action may
have occurred, but there is no valid readback from which to claim either
success or inertness.

## Authority and receipt

The action uses `owner_standing` authority and never asks for per-action
confirmation. It does require `embodiment_lease_id` so only one session owns the
lease-mediated Mac write channel. A transaction-scoped action mutex is held
from lease validation through independent postflight and receipt persistence,
so even the same session cannot interleave two lease-mediated body mutations.
The lease and mutex are concurrency controls, not additional permission
ceremonies.

The durable semantic-event store is an admission prerequisite. After all
pre-spawn checks pass, the owned action guard and admitted inputs move into a
detached supervisor. Before spawning Swift, the supervisor must successfully
append an `action_started` write-ahead marker with the transaction ID, target,
lease, assets, and toolchain binding. Failure to persist that marker dispatches
nothing. The marker records that dispatch had not yet occurred at marker time;
attempted/performed remain unknown until a terminal receipt closes the same
transaction. It is a separate event kind, so it cannot close an intent or win a
same-second projection race against the terminal `action_receipt`.

An MCP cancellation before the supervisor barrier dispatches nothing;
cancellation after it only abandons the response waiter while the supervisor
completes process cleanup, verification, and terminal receipt persistence. A
caught post-spawn panic is persisted as `Unknown`. If the daemon or store fails
after dispatch and before terminal persistence, the durable start marker remains
as explicit evidence of an unclosed transaction instead of silently losing the
action from the audit trail.

The mutex is shared with existing lease-mediated terminal and browser writes.
Protocol-level media control remains a separate non-window lane: it does not
activate applications or alter the AX foreground/window target used by this
transaction. Bringing a future application-activation primitive into the AX
lane requires the same lease, mutex, and durable receipt contract.

The receipt binds:

- body, lease, optional intent, bundle, PID, and target identity digest;
- before/after semantic world revisions;
- attempted/performed/idempotent execution truth;
- primitive and AX error;
- exact postcondition and foreground result;
- the complete independent verifier evidence (or an explicit skipped reason);
- executor, verifier, and probe asset SHA-256 values;
- the sanitized developer-dir resolution, Apple signing identifiers, real
  invocation/canonical paths, and executable SHA-256 values;
- source and independent receipt SHA-256 values; and
- a UUID transaction ID plus a separately hash-bound audit object covering the
  body, lease, optional intent, target, assets, receipts, and pinned toolchain.

`transaction_core_sha256` covers the transaction envelope before the MCP
wrapper is attached. `audit_binding_sha256` covers the explicit audit binding.
The returned wrapper separately reports whether the terminal action receipt
reached the embodiment event store; that post-record result is intentionally
not claimed as part of either earlier digest. Both normal and exceptional
terminal facts use `phase_seq=1`; the pre-dispatch marker uses `phase_seq=0`.
`transaction_closed` is true only after the terminal record succeeds. If that
write fails, the MCP result is marked as an error even when the semantic effect
was independently verified; callers must reconcile the surviving start marker
and must not blindly retry the already-observed action.

Only agreement between the executor postcondition and independent verifier
records `VerdictStatus::Verified`. A valid independent negative readback records
`VerdictStatus::NotVerified`. Any post-spawn timeout, invalid executor receipt,
unavailable/invalid independent readback, foreground drift, unreadable
postflight, or setter error after dispatch records `VerdictStatus::Unknown`.
The executor preserves the strongest truthful performed value it has; wrapper
failures without a valid executor receipt use `attempted=true` and
`performed=null`. Neither path claims that the action was not attempted.
Optional intent linkage is persisted under the native projection's `intent_id`
contract.

## Exposure and release gates

The tool is Niche tier and explicitly available on the Codex essential Apple
host surface. This keeps the generic Standard profile bounded without hiding
the body capability from its primary user.

Source verification, default-branch merge, deployment, MCP reconnect, and a
real-window acceptance action remain separate gates. This change does not
perform a live focus action by itself.
