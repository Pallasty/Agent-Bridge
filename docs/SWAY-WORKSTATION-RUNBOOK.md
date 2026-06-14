# Sway Workstation Runbook

This runbook covers the local Sway workstation integration managed by Agent-Bridge.
It is intentionally operational: use it to reinstall, verify, and troubleshoot the
keyboard shortcuts, status bar actions, display power policy, and desktop watchdog.

## Install Or Refresh

The canonical setup script is:

```sh
/Data/CascadeProjects/agent-bridge/scripts/setup-sway-workstation.sh
```

The user-facing copy is kept in sync at:

```sh
/Programs/Users/Pallasting/Documents/Sway/setup-sway-workstation.sh
```

Run the setup script after a fresh Sway install, after changing hotkeys, or after
changing one of the helper scripts generated under `~/.local/bin`.

## What It Manages

- Sway hotkeys for volume, microphone mute, brightness, display mode, airplane
  mode, media play/pause, calculator, favorites, and region screenshot.
- Mako notifications with automatic expiry.
- Swayidle display blanking without suspend or sleep.
- Lid-close behavior that turns displays off without suspending.
- Power button behavior: single press blanks display; quick double press powers off.
- Clickable status bar blocks for Wi-Fi and Agent-Bridge actions.
- Battery status with `+BAT` when charging.
- Desktop doctor, heal, watchdog, snapshot history, diagnosis, and status report.

## Daily Checks

Run a compact Agent-Bridge health check:

```sh
~/.local/bin/agent-bridge.real doctor
```

Run the desktop-specific doctor:

```sh
~/.local/bin/ab-system-control desktop doctor | jq .
```

Open the human-readable status report:

```sh
~/.local/bin/ab-system-control status report 20
```

Inspect trend diagnosis:

```sh
~/.local/bin/ab-system-control status diagnose 20 | jq .
```

## Watchdog

The watchdog is installed as:

```sh
~/.local/bin/sway-desktop-watchdog
```

It is normally run by the user systemd timer:

```sh
systemctl --user status sway-desktop-watchdog.timer
```

Each watchdog run:

1. Runs the desktop doctor.
2. Records a compact status snapshot.
3. Runs desktop heal when the doctor reports a non-ok state and the heal cooldown
   has expired.
4. Sends a desktop notification only when the current diagnosis is degraded or
   watch-worthy.

Useful environment switches:

```sh
SWAY_DESKTOP_WATCHDOG_COOLDOWN=600
SWAY_DESKTOP_WATCHDOG_RECORD_SNAPSHOT=1
SWAY_DESKTOP_WATCHDOG_NOTIFY=1
SWAY_DESKTOP_WATCHDOG_NOTIFY_COOLDOWN=1800
SWAY_DESKTOP_WATCHDOG_NOTIFY_RECENT=0
SWAY_DESKTOP_WATCHDOG_DIAGNOSE_LINES=20
```

`recent_degradation` is intentionally not notified by default. It means the latest
snapshot is healthy, but recent history includes a recovered problem.

## Status Data

Audit and status files live under:

```sh
/Data/agent-bridge/system-control/
```

Important files:

- `system-actions.jsonl`: audited system-control actions.
- `system-events.jsonl`: lightweight event log from status bar, watchdog, and helpers.
- `system-snapshots.jsonl`: compact rolling health snapshots.
- `sway-desktop-watchdog.last_heal`: heal cooldown marker.
- `sway-desktop-watchdog.last_notify`: notification cooldown marker.

The directory should be mode `700`; sensitive logs should be mode `600`.

## Common Recovery Commands

Repair desktop services and reload the Sway environment:

```sh
~/.local/bin/ab-system-control desktop heal --confirm
```

Run the watchdog immediately:

```sh
~/.local/bin/ab-system-control desktop watchdog
```

Show the latest audit actions:

```sh
~/.local/bin/ab-system-control audit tail
```

Open the Agent-Bridge status menu from the status bar by left-clicking the `AB`
block. Middle-click shows status summary; right-click opens audit output.

## Expected Healthy State

At the time this runbook was added, a healthy machine reports:

- `agent-bridge.real doctor`: `9 ok / 0 warn / 0 fail`
- `desktop doctor`: `40 ok / 0 warn / 0 fail`
- `status report`: latest `desktop=ok`, `watchdog=ok`, services all `ok`

If `status report` shows `recent_degradation` but the latest line is healthy, the
system recovered. It should clear naturally as newer healthy snapshots roll in.
