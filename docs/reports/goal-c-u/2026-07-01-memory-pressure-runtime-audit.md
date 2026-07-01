# Memory Pressure Runtime Audit

Date: 2026-07-01

Status: read-only runtime audit / no process kill / no config change

## Summary

The post-OOM/interruption readout does not show a current Agent-Bridge runaway
or a kernel OOM kill.

The strongest evidence points to Chromium/Electron-family client processes as
the memory-pressure source. Systemd user journal recorded multiple
Chromium-named scopes with multi-GB memory peaks, including one 9.9 GB memory
peak and 6.9 GB swap peak at 13:42.

Agent-Bridge services were healthy during the audit. The only sizeable
Agent-Bridge process was `daemon-http`, which owns the single local embedding
model instance after daemon embedding delegation.

## Current Memory State

Snapshot:

```text
Mem: 15Gi total, 9.5Gi used, 2.1Gi free, 5.3Gi buff/cache, 5.9Gi available
Swap: 11Gi total, 6.3Gi used
zram0: 7.7Gi total, 6.2Gi used
/swap.img: 4.0Gi total, 189Mi used
load average: 2.70, 2.48, 4.09
```

Pressure at audit time was low:

```text
/proc/pressure/memory:
some avg10=0.00 avg60=0.00 avg300=0.05
full avg10=0.00 avg60=0.00 avg300=0.05
```

`vmstat 1 5` showed no sustained swap-out storm during the audit. There was
minor swap-in activity while the system still had about 6.3 GiB of swap already
occupied.

## Current RSS Leaders

Top process-family RSS aggregate by command name:

| Family | Count | RSS |
|---|---:|---:|
| `cursor` | 33 | 3781 MiB |
| `chrome` | 23 | 2176 MiB |
| `codex` | 6 | 775 MiB |
| `agent-bridge.real` | 14 | 739 MiB |
| `node-MainThread` | 11 | 405 MiB |
| `WeChatAppEx` | 11 | 218 MiB |
| `claude` | 2 | 202 MiB |

The broader argv-based grouping overlaps categories such as node-backed Codex
and Cursor workers, but it confirms the same shape: Electron/browser clients
dominate resident memory, not Rust build jobs or Agent-Bridge services.

No `cargo` or `rustc` process was running during the audit.

## Agent-Bridge Service Readout

Systemd user services:

| Service | State | Main PID | MemoryCurrent |
|---|---|---:|---:|
| `agent-bridge-daemon.service` | active/running | 205569 | 16.5 MB |
| `agent-bridge-daemon-http.service` | active/running | 205570 | 535 MB |
| `agent-bridge-palace.service` | active/running | 205571 | 25.4 MB |

`smaps_rollup` for the service processes:

| Process | RSS | PSS | Private | Swap |
|---|---:|---:|---:|---:|
| `agent-bridge.real daemon` | 8.2 MiB | 4.6 MiB | 3.1 MiB | 3.3 MiB |
| `agent-bridge.real daemon-http` | 510.2 MiB | 505.2 MiB | 503.1 MiB | 787.2 MiB |
| `agent-bridge.real palace` | 28.1 MiB | 24.0 MiB | 22.0 MiB | 5.2 MiB |

Interpretation:

- `daemon-http` is the expected local embedding owner.
- `daemon` is not double-loading the model; its PSS is only about 4.6 MiB.
- MCP stdio `agent-bridge.real mcp` children were small, mostly around 1-13 MiB
  PSS each.

MCP lifecycle was healthy:

```text
lifecycle_state=ready
readiness_warnings=0
runtime_health_status=ready
failing_tool_count=0
```

## OOM / Crash Evidence

Kernel journal search for the last six hours found no matching lines for:

- `out of memory`
- `oom`
- `killed process`
- `invoked oom-killer`
- `memory cgroup`

`systemd-oomd.service` is not installed on this host.

Agent-Bridge service journals for the last six hours had no service-local crash
entries under the three core units.

The relevant user-journal evidence is instead Chromium/Electron memory peaks:

```text
11:25 app-org.chromium.Chromium-116175.scope:
  9.3G memory peak, 6.1G memory swap peak

11:29 app-org.chromium.Chromium-1223515.scope:
  4.9G memory peak

13:42 app-org.chromium.Chromium-1240137.scope:
  9.9G memory peak, 6.9G memory swap peak
```

Current cgroup readout also showed the user app slice dominated by a
Chromium-named Electron scope:

```text
user.slice/user-1000.slice/user@1000.service/app.slice: 6.6G
app-org.chromium.Chromium-1904273.scope: 5.6G
agent-bridge-daemon-http.service: 509.8M
agent-bridge-daemon.service: 16.4M
agent-bridge-palace.service: 25.8M
```

## Secondary Finding: Systemd Unit Permissions

The user journal repeatedly reports Agent-Bridge unit/drop-in files as
executable and world-writable. Current file-mode scan showed mode `777` for
Agent-Bridge user services, timers, and the INT8 drop-ins under
`~/.config/systemd/user`.

This is not an OOM root cause, but it is noisy and weakens operational hygiene.
It is a good small reversible follow-up:

```text
chmod 644 ~/.config/systemd/user/agent-bridge*.service
chmod 644 ~/.config/systemd/user/agent-bridge*.timer
chmod 644 ~/.config/systemd/user/agent-bridge*.service.d/*.conf
systemctl --user daemon-reload
```

Symlinks under `*.target.wants/` naturally appear as mode `777` and do not need
chmod.

## Recommendation

Do not open an Agent-Bridge RAM-reduction implementation lane from this audit.
The earlier ArrowQuant / GTE double-load work is still paying off: daemon
embedding delegation keeps `agent-bridge-daemon` tiny, and only `daemon-http`
owns the remaining model footprint.

Recommended next action:

1. Fix the Agent-Bridge user unit file modes as a small hygiene patch.
2. If memory pressure recurs, capture the active Chromium/Electron scope before
   closing/restarting it:
   `systemd-cgtop -b -n1 --depth=8` and `ps -eo pid,ppid,rss,comm,args --sort=-rss | head -80`.
3. Consider closing or restarting stale/high-RSS Cursor/Chromium windows only
   as an operator action, not as an Agent-Bridge code fix.

## Boundary

This audit did not:

- kill or restart any process;
- edit systemd units or environment files;
- change Agent-Bridge runtime configuration;
- deploy a binary;
- run graph writes or memory writes;
- change retrieval ranking, tool routing, prompts, profiles, or MCP exposure.
