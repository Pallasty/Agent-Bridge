# macOS AX focus continuity dogfood

## Outcome

This candidate tests whether an exact, low-risk window-focus intent can survive
a caller interruption without a second focus dispatch. It reuses the existing
`macos_ax_probe`, `macos_ax_action_admission`, `embodiment_lease`,
`macos_ax_focus_transaction`, and `macos_ax_verify` contracts. The first stage
adds no public tool and performs no live action.

The existing focus transaction is already bounded and independently verified,
but its persisted marker explicitly says `resumes_action=false` and every call
gets a new transaction ID. Therefore it is a safe transaction primitive, not a
restart-continuous episode by itself.

## Exact scope

The first slice permits only `focus_window` within the already-frontmost app.
The target is `bundle_id + pid + stable AXIdentifier`, corroborated by exact
role and optional exact title. Cross-app activation, sample-local window index,
coordinates, typing, buttons, screen pixels, arbitrary scripts, background
polling, and protected or external effects remain out of scope.

Live admission requires all of the following:

- Darwin, AX trusted, and no permission prompt;
- a complete, untruncated `macos_ax_probe/v0` receipt no older than 5 seconds;
- one frontmost app with exact bundle ID and PID;
- two distinct windows in that app with unique stable AXIdentifiers;
- complete selector reads and no hidden or unknown candidates;
- the target window is not currently focused;
- owner-standing rank-1 navigation admission;
- a current exclusive embodiment lease; and
- a writable owner-only episode journal.

If the Mac cannot provide this surface naturally, the pair is ineligible. The
runner must not create windows, activate another app, loosen selectors, or use
titles as identity to manufacture eligibility.

## Episode state machine

The future private runner uses a caller-supplied operation ID and a canonical
request binding. Its durable phases are:

1. `prepared`: exact target and complete probe receipt are bound;
2. `dispatch_started`: persisted before calling the focus transaction;
3. `effect_verified`: exact target focus independently observed;
4. `terminal`: receipt and cleanup are durable.

Fresh execution may dispatch focus only after `dispatch_started` is durable.
Any same-ID call at or beyond `dispatch_started` must never call
`macos_ax_focus_transaction` again. It performs only a fresh
`macos_ax_verify(expect=window_focused)` using the exact bundle, PID,
AXIdentifier, role, and title contract. A verified recovery records
`causal_attribution=unknown_after_interruption`; false, incomplete, stale,
scope-changed, or unreadable evidence returns reobserve/replan without a second
dispatch.

The embodiment lease and action lock must remain supervised until the original
focus transaction and its receipt persistence finish, even if the runner loses
its response. The recovery invocation acquires no write lease because it is
read-only. TTL expiry, request conflict, corrupt journal, or unknown dispatch
phase never causes automatic operation-ID replacement.

## Paired measurement

The baseline is five agent-visible calls:

1. probe exact target;
2. preview action admission;
3. acquire embodiment lease;
4. execute focus transaction;
5. release embodiment lease.

The trial is two runner invocations with one operation ID:

1. prepare, persist `dispatch_started`, invoke the transaction, then inject a
   registered response-loss boundary after the executor has started;
2. restart the runner and recover by read-only exact focus verification.

Each side must end with the same semantic postcondition and verified lease
cleanup. Gating metrics are owner restatements, manual interventions,
agent-visible calls, and failed or replanned calls. Elapsed time is descriptive
only. A pair with response-loss injection that cannot prove the executor start
marker, exact target, postcondition, or cleanup is aborted and excluded.

## Claim boundary

Three useful paired tasks may support a workflow-burden conclusion and owner
review. They do not prove general computer-use skill, exclusive causation,
pixel correctness, human observation, cross-app navigation, or safe replay of
content-changing actions. No implementation or live execution is authorized
until the design preregistration and its closed validator are merged.

## Offline implementation gate

After the design gate merged, the owner authorized the next bounded candidate.
The first implementation remains private and source-local:

- `macos-ax-focus-continuity-collector.py` validates complete two-window probe,
  admission, focus-transaction, recovery-verifier, and terminal receipts;
- `macos-ax-focus-continuity-runner.py` owns an operation-ID-hashed, 0700/0600,
  flock-serialized and fsync/rename-persisted journal;
- a fresh invocation may call the focus transaction once only after persisting
  `dispatch_started` with `dispatch_count=1`;
- registered response loss leaves that record nonterminal, releases the lease,
  and returns `retry` without claiming the effect;
- a later same-ID invocation calls only `macos_ax_verify(window_focused)` and
  records `causal_attribution=unknown_after_interruption` on success; and
- terminal replay performs no MCP calls and rejects malformed stored receipts.

The runner is not a public MCP tool and is not a deployed runtime asset. This
implementation gate does not authorize a real Mac focus action. Read-only Mac
eligibility inspection, live fault injection, paired measurement, and rollout
remain distinct owner gates.

## First read-only Mac eligibility gate

The owner subsequently authorized only the read-only eligibility inspection.
The merged probe bytes were streamed to the Mac system Python without writing
a remote file, and the raw receipt was piped directly through the content-free
eligibility reducer. At the observation time, AX trust was true and no prompt
was requested, but `System Events` was not running. The no-ask preflight
correctly refused to start it, so the probe returned degraded with no complete
window surface. Finder was running, but no window identity was retained.

The result is `INELIGIBLE_NO_LIVE_ACTION`. The gate did not start System Events,
activate an app, create a window, acquire a lease, invoke focus, or retain raw
window titles. This negative result is a successful fail-closed gate, not a
failed experiment and not authority to manufacture eligibility.

## Native AX follow-up

The next authorized implementation removed `System Events` from the
eligibility observation itself. A source-local Swift probe used only
`NSWorkspace` and read-only `AXUIElementCopyAttributeValue` calls. It was
streamed to the Mac Swift interpreter and its raw JSON was again piped directly
through the content-free reducer.

This native path successfully observed a complete, untruncated two-window
surface with consistent counts. Both windows exposed title, role, and focused
state, but neither exposed a non-empty `AXIdentifier`. The result therefore
remains `INELIGIBLE_NO_STABLE_WINDOW_IDENTITY`. The experiment does not fall
back to title, sample index, coordinates, pixels, or a different application.
No focus action or application-state mutation was performed.
