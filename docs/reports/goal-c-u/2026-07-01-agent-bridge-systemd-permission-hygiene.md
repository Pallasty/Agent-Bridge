# Agent-Bridge systemd permission hygiene

Date: 2026-07-01

Follow-up to:
`docs/reports/goal-c-u/2026-07-01-systemd-unit-permission-hygiene-attempt.md`

## Summary

The Agent-Bridge user systemd permission warnings were cleaned up without
changing unit content or restarting services.

The original simple fix, `chmod 644 ~/.config/systemd/user/agent-bridge*`,
did not stick because `/home` is mounted as `fuseblk` and exposes files under
`~/.config/systemd/user` as `root:root 777`.

The deployed unit/timer files were byte-for-byte identical to the tracked
sources under `scripts/systemd/`, so the durable fix was to keep the real files
on `/Data` and replace the `/home` unit files with symlinks.

## Changes Applied

- Backed up the previous deployed files to:
  - `.agent-bridge/systemd-user/backups/20260701-141807`
- Replaced these `~/.config/systemd/user` files with symlinks to
  `/Data/CascadeProjects/agent-bridge/scripts/systemd/`:
  - `agent-bridge-daemon-http.service`
  - `agent-bridge-daemon.service`
  - `agent-bridge-memory-decay-unused.service`
  - `agent-bridge-memory-decay-unused.timer`
  - `agent-bridge-palace.service`
  - `agent-bridge-sync.service`
  - `agent-bridge-sync.timer`
- Copied the local int8 model drop-ins to:
  - `.agent-bridge/systemd-user/agent-bridge-daemon.service.d/int8-model.conf`
  - `.agent-bridge/systemd-user/agent-bridge-daemon-http.service.d/int8-model.conf`
- Replaced the `/home` drop-in files with symlinks to those local `/Data`
  copies.
- Ran `systemctl --user daemon-reload`.

## Verification

Resolved target modes now report as regular `644` files owned by
`pallasting:pallasting`:

```text
agent-bridge-daemon-http.service: 644
agent-bridge-daemon.service: 644
agent-bridge-memory-decay-unused.service: 644
agent-bridge-memory-decay-unused.timer: 644
agent-bridge-palace.service: 644
agent-bridge-sync.service: 644
agent-bridge-sync.timer: 644
agent-bridge-daemon-http.service.d/int8-model.conf: 644
agent-bridge-daemon.service.d/int8-model.conf: 644
```

Runtime state after reload:

```text
agent-bridge-daemon.service: active/running
agent-bridge-daemon-http.service: active/running
agent-bridge-palace.service: active/running
agent-bridge-sync.timer: active/waiting
agent-bridge-memory-decay-unused.timer: active/waiting
```

A fresh `systemctl --user daemon-reload` no longer emitted Agent-Bridge
permission warnings.

Remaining warnings are outside this Agent-Bridge fix:

- `~/.config/autostart/ssh-config-restore.desktop`
- `~/.config/autostart/touchpad-tune.desktop`
- `~/.config/systemd/user/sway-desktop-watchdog.service`
- `~/.config/systemd/user/sway-desktop-watchdog.timer`

## Rollback

To roll back, replace the Agent-Bridge symlinks under
`~/.config/systemd/user` with files from
`.agent-bridge/systemd-user/backups/20260701-141807`, then run:

```bash
systemctl --user daemon-reload
```
