# Museum

Code that's no longer compiled into the workspace, kept here as historical
reference. Each subdirectory holds one retired component along with a short
note on what replaced it and why.

This is intentionally outside the Cargo workspace — `cargo build` won't see
the files, so the museum has zero runtime / build-time cost. You can still
read, grep, or copy fragments back to a live crate if a corner case turns
out to need the old behaviour.

| Subdirectory | Replaced by | Retired in |
|---|---|---|
| `warp-ipc-terminal/` | `PtyBackend` + OSC 133 prompt protocol — see `docs/SHELL-INTEGRATION-OSC133.md`. The `warp_open_*` MCP tools and `warp_status` keep working via `crates/bridge/src/warp_scheme.rs` (URL-scheme launchers only, no IPC). | 2026-05-08, after the four-phase Warp drop migration (`c2ba69c`, `1744cb8`, `b968bfd`, `2f14d84`). |
