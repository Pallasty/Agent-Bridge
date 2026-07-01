# Systemd Unit Permission Hygiene Attempt

Date: 2026-07-01

Status: attempted / blocked by host filesystem permissions semantics / no service restart

## Summary

The memory-pressure runtime audit identified noisy Agent-Bridge user systemd
unit permissions: user unit, timer, and drop-in files under
`~/.config/systemd/user` are reported by systemd as executable and
world-writable.

The bounded follow-up was attempted:

```text
chmod 644 ~/.config/systemd/user/agent-bridge*.service
chmod 644 ~/.config/systemd/user/agent-bridge*.timer
chmod 644 ~/.config/systemd/user/agent-bridge*.service.d/*.conf
systemctl --user daemon-reload
```

`systemctl --user daemon-reload` completed, but the mode change did not persist.
The files still report mode `777`, and the user journal still emits the same
systemd warnings.

## Blocking Evidence

The affected files are regular files, not symlinks:

```text
777 regular file /home/pallasting/.config/systemd/user/agent-bridge-daemon.service
777 regular file /home/pallasting/.config/systemd/user/agent-bridge-daemon-http.service
777 regular file /home/pallasting/.config/systemd/user/agent-bridge-daemon.service.d/int8-model.conf
777 regular file /home/pallasting/.config/systemd/user/agent-bridge-daemon-http.service.d/int8-model.conf
```

The host path is backed by a `fuseblk` mount with root ownership semantics:

```text
/home /dev/nvme0n1p5 fuseblk rw,relatime,user_id=0,group_id=0,allow_other,blksize=4096
```

The current user is `pallasting` and belongs to the `sudo` group, but
non-interactive sudo is not available:

```text
sudo: interactive authentication is required
sudo_status=1
```

Interpretation: the straightforward chmod remediation is not currently
actionable from this agent session. A durable fix likely requires an operator
or host-level change, such as moving user systemd config to a Linux-native
filesystem with normal mode persistence, changing the mount permissions
semantics, or applying root-assisted ownership/mode repair.

## Service Safety Check

After the attempted chmod and daemon reload, the core Agent-Bridge services
remained active/running:

```text
agent-bridge-daemon.service: active/running, MainPID=205569
agent-bridge-daemon-http.service: active/running, MainPID=205570
agent-bridge-palace.service: active/running, MainPID=205571
```

No process kill, restart, binary deploy, environment change, or Agent-Bridge
runtime config change was performed.

## Boundary

This follow-up did not change memory DB contents, graph edges, retrieval
ranking, MCP profiles, tool routing, prompts, service definitions, or daemon
runtime environment. It only attempted file mode repair and reloaded the user
systemd manager.
