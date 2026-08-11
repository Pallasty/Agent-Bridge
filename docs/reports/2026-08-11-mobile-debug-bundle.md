# Mobile Debug Bundle — 2026-08-11

## Outcome

`mobile_debug_bundle` turns a repeated multi-command Android diagnosis into one
bounded, read-only collection call. The compact MCP response points to a local
manifest and artifacts instead of returning their full contents into agent
context.

The bundle contains focus state, package details when a package is supplied or
can be inferred, bounded recent logcat, `data_app_crash` Dropbox excerpts, UI
XML, and an opt-in screenshot. Each source has an independent status, so one
unavailable source produces a useful `partial` bundle rather than losing the
successful evidence.

The output parent must already exist, the tool always creates a unique child,
and it refuses collisions. On Unix the directory is `0700` and files are
`0600`. Screenshot capture defaults off.

## Physical-device acceptance

Device `3K661F0178H00000` was connected over authorized USB. A source-built MCP
collected 80 recent log lines with UI and crash evidence enabled and screenshot
disabled. It inferred the foreground package `com.android.launcher` and wrote:

- `manifest.json`
- `focus.txt`
- `package.txt`
- `logcat.txt`
- `crash-dropbox.txt`
- `ui.xml`

All five requested evidence sources reported `ok`; the screenshot entry
reported `skipped` as requested. No application was launched, stopped, or
clicked.

## Validation

- `cargo check -p ab-bridge --lib`
- `cargo build -p ab-bridge --bin agent-bridge`
- `cargo test -p ab-bridge 'mobile_' --lib` — 19 passed
- `git diff --check`
- source-built MCP registry count increased from 101 to 102
- live bundle collection and manifest inspection — passed
