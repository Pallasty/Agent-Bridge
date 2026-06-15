#!/usr/bin/env bash
set -euo pipefail

checkout="${1:-}"

if [ -z "$checkout" ]; then
    echo "BioCortex checkout hygiene preflight: missing checkout path argument." >&2
    exit 2
fi

if [ ! -f "$checkout/Cargo.toml" ]; then
    echo "BioCortex checkout hygiene preflight: Cargo.toml not found at $checkout." >&2
    echo "Set AB_BIOCORTEX_RS=/path/to/a/clean/biocortex-rs checkout." >&2
    exit 2
fi

if ! git -C "$checkout" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "BioCortex checkout hygiene preflight: $checkout is not a git checkout." >&2
    echo "Use a clean, synced biocortex-rs git worktree and set AB_BIOCORTEX_RS to it." >&2
    exit 2
fi

dirty_status="$(git -C "$checkout" status --porcelain --untracked-files=all)"
if [ -n "$dirty_status" ]; then
    echo "BioCortex checkout hygiene preflight: checkout is dirty: $checkout" >&2
    echo "Commit/stash/revert these files, or set AB_BIOCORTEX_RS to a clean verification worktree." >&2
    printf '%s\n' "$dirty_status" | sed 's/^/  /' >&2
    exit 2
fi

branch_status="$(git -C "$checkout" status --short --branch --untracked-files=no 2>/dev/null || true)"
if printf '%s\n' "$branch_status" | grep -Eq '\[[^]]*ahead [0-9]+, behind [0-9]+'; then
    echo "BioCortex checkout hygiene preflight: checkout has diverged from its upstream: $checkout" >&2
    echo "Resolve the divergence or set AB_BIOCORTEX_RS to a clean up-to-date verification worktree." >&2
    printf '%s\n' "$branch_status" | sed 's/^/  /' >&2
    exit 2
fi

if printf '%s\n' "$branch_status" | grep -Eq '\[[^]]*behind [0-9]+'; then
    echo "BioCortex checkout hygiene preflight: checkout is behind its upstream: $checkout" >&2
    echo "Fast-forward it or set AB_BIOCORTEX_RS to a clean up-to-date verification worktree." >&2
    printf '%s\n' "$branch_status" | sed 's/^/  /' >&2
    exit 2
fi
