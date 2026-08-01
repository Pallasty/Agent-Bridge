# S5ZY secure Story machine-env relocation

The live machine environment now resides at
`/home/pallasting/.agent-bridge-secure/machine.env` on the ext4 root
filesystem. Its parent is owner-only `0700` and the file is `0600`, owned by
`pallasting`. The existing wrapper-compatible path remains unchanged from the
caller's perspective but is now a symbolic link to the secure target.

Content SHA-256 stayed `520dd17c...f51c3`. The previous NTFS/FUSE file remains
at `machine.env.pre-s5zy-520dd17c` for rollback. A temporary current-source MCP
probe again observed Story absent under `standard` and present under `all`.
Seven persistent installed MCP processes were left untouched, and the installed
binary remains the pre-Story `5a02c8fd` build.

The permissions blocker is closed. A guarded deployment dry-run is now
admitted, but a real deployment, MCP restart, and client refresh are not.
