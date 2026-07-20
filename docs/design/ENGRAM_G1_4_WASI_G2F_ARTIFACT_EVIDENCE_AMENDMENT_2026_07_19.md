# G2F artifact-evidence amendment

Forum #4783 records the owner-confirmed continuation after G2G's independent
failure verdict #4780 and fail-closed record #4781. The amendment changes evidence interpretation only: an `.rlib` SHA
is a per-build observation, not a cross-worktree reproducibility claim, because
Rust archives contain target-path-related bytes.

G2G acceptance now requires: exact G2E host-source SHA, exact zero-dependency
manifest and lockfile SHA, declared rustc/cargo identity, an offline locked
command, independent successful compile, target removal, and proof that no
output was run. Each build still records its raw artifact SHA, but differing
SHA values across isolated target directories are fail-closed evidence of
non-portability—not a build failure.

No authority changes: run, network, dependency, WIT/component/linker,
runtime/MCP/deploy/canary, native/QEMU, and G1.4 remain forbidden.
