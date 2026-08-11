# Mobile Wait for UI — 2026-08-11

## Outcome

`mobile_wait_for_ui` provides a bounded, read-only synchronization primitive
for Android workflows. It replaces fixed sleeps and repeated snapshots after
explicit install, launch, consent, or navigation actions.

The tool accepts the existing full UI selector shape and waits for `present`
or `absent`. Callers can require one to five consecutive matching snapshots to
avoid accepting a transient overlay. Successful responses contain compact
matched nodes and UI-tree analysis; timeout responses retain attempt count,
last match count, stability progress, and the last snapshot error.

The total `wait_timeout_ms` is enforced around UI snapshot work as well as
polling sleeps. A slow UIAutomator call therefore cannot silently extend the
requested wait budget. The existing `timeout_ms` remains the independent
per-ADB ceiling.

## Physical-device acceptance

On authorized serial `3K661F0178H00000`, the tool waited for launcher resource
ID `com.android.launcher:id/launcher` with `stable_polls=2`. It matched on the
second snapshot, returned the compact FrameLayout node, and reported a semantic
35-node UI tree.

A missing text marker was then tested with a 3,000 ms total budget. It returned
`status=timeout`, two attempts, zero matches, and `elapsed_ms=3001`, confirming
the total deadline is enforced rather than being overrun by UIAutomator. No
screen click, application launch, input, or screenshot occurred.

## Validation

- `cargo check -p ab-bridge --lib`
- `cargo build -p ab-bridge --bin agent-bridge`
- `cargo test -p ab-bridge 'mobile_' --lib` — 21 passed
- `git diff --check`
- source-built MCP registry increased from 102 to 103 tools
- physical-device stable-present and hard-timeout paths — passed
