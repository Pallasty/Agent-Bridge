# Sway Workstation Change Packet - 2026-06-12

## Scope

This packet captures the local Sway workstation integration work:

- Keyboard hotkeys for volume, mic mute, brightness, display mode, airplane
  mode, media play/pause, calculator, favorites, and region screenshots.
- Clickable status bar actions for Wi-Fi and Agent-Bridge.
- Battery charging label using `+BAT`.
- Display blanking without suspend, lid-close display-off behavior, and guarded
  power-button handling.
- Audited `ab-system-control` actions exposed to MCP through the allowlisted
  `system_control` tool.
- Desktop doctor/heal/watchdog scripts, user systemd timer, status snapshots,
  trend diagnosis, human-readable report, and throttled degradation notices.
- Operator runbook at `docs/SWAY-WORKSTATION-RUNBOOK.md`.

## Files

Primary Sway/system-control files:

- `scripts/setup-sway-workstation.sh`
- `scripts/ab-system-control.sh`
- `scripts/sway-desktop-doctor.sh`
- `scripts/sway-desktop-watchdog.sh`
- `scripts/systemd/sway-desktop-watchdog.service`
- `scripts/systemd/sway-desktop-watchdog.timer`
- `docs/SWAY-WORKSTATION-RUNBOOK.md`

Agent-Bridge integration files:

- `crates/bridge/src/mcp_tools.rs`
- `crates/bridge/src/doctor.rs`
- `README.md`

Compatibility fixes needed by the current dirty worktree:

- `crates/bridge/src/lib.rs`: raises macro recursion limit for existing large
  BioCortex JSON payloads.
- `crates/bridge/src/biocortex_shadow.rs` and `crates/bridge/src/mcp_tools.rs`:
  pass through the existing `evidence_summary` option so current BioCortex
  changes compile.

## Installed State

- `/Programs/Users/Pallasting/Documents/Sway/setup-sway-workstation.sh` matches
  the repo setup script.
- `~/.local/bin/sway-desktop-watchdog` matches the repo watchdog script.
- `sway-desktop-watchdog.timer` is enabled and active.

## Verification

Commands run successfully:

```sh
bash -n scripts/ab-system-control.sh scripts/sway-desktop-doctor.sh scripts/sway-desktop-watchdog.sh scripts/setup-sway-workstation.sh
cargo test -p ab-bridge doctor::tests -- --nocapture
cargo test -p ab-bridge system_control -- --nocapture
~/.local/bin/agent-bridge.real doctor
~/.local/bin/ab-system-control desktop doctor
~/.local/bin/ab-system-control status report 20
```

Observed healthy state:

- `agent-bridge.real doctor`: `9 ok / 0 warn / 0 fail`
- `desktop doctor`: `40 ok / 0 warn / 0 fail`
- Latest status snapshot: `desktop=ok`, `watchdog=ok`, services all `ok`

`status report` may temporarily show `recent_degradation` because the test run
created a recovered warning snapshot. The latest state is healthy, and default
watchdog notifications ignore recovered historical degradation.

## Notes

Global `cargo fmt --check` is currently noisy because unrelated files in the
worktree require formatting. This packet avoids applying whole-repo formatting
to keep the Sway workstation change scoped.
