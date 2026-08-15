# S5ZX Story fixture configuration installation

The 12-key fixture-pilot fragment was appended exactly to the machine-local
environment. The original file is recoverable from
`machine.env.bak-s5zx-9291d52f`. A temporary current-source MCP probe kept the
tool hidden under `standard` and observed `story_command_preflight` under
`all`; no persistent MCP process was restarted.

Runtime adoption remains blocked. `~/.config` resolves into the `/Media`
NTFS/FUSE mount, where the file continues to report `0777 root:root` after an
attempted `chmod 600` and user-owned atomic replacement. Because this file is
sourced as shell, the inability to enforce owner-only permissions is a code
injection boundary, even though the Story fragment itself contains no secret.

The next gate is a relocation review for a POSIX-backed, owner-controlled
machine environment path. No binary was deployed and no client was refreshed.
