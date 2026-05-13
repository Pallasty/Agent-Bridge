#!/usr/bin/env bash
# Wire repo-level git hooks. Run once per clone (and any time .githooks/
# gains a new hook — re-running is idempotent).
#
# What it does:
#   - `git config core.hooksPath .githooks`  → tells git to look in our
#     repo-tracked .githooks dir instead of the default .git/hooks.
#   - Ensures executable bits (in case the working tree lost +x).
#
# Why repo-level (not .git/hooks): tracked in source, so every clone
# gets the same hooks once they run this script. Sister machines pull
# updates via `git pull` rather than copy-pasting from a stale README.
#
# Bypassing the hooks (emergencies):
#   git commit --no-verify ...
#   AGENT_BRIDGE_SKIP_PRECOMMIT=1 git commit ...
#
# Repo onboarding flow:
#   git clone <repo>
#   ./scripts/install-githooks.sh
#   ./scripts/wrapper/install.sh    # also bootstraps wrapper + creds
#
# (The wrapper installer at scripts/wrapper/install.sh now invokes
#  this script too, so a clean onboard = wrapper install + done.)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "error: not inside a git repository" >&2
    exit 1
fi

HOOKS_DIR_REL=".githooks"
HOOKS_DIR_ABS="$REPO_ROOT/$HOOKS_DIR_REL"

if [[ ! -d "$HOOKS_DIR_ABS" ]]; then
    echo "error: $HOOKS_DIR_ABS missing — is this the right repo?" >&2
    exit 1
fi

echo "→ git config core.hooksPath $HOOKS_DIR_REL"
git -C "$REPO_ROOT" config core.hooksPath "$HOOKS_DIR_REL"

# Re-stamp executable bit on every hook — clones may land with 0644
# on systems where chmod doesn't survive the round-trip (rare on
# linux/macOS but observed under WSL).
for hook in "$HOOKS_DIR_ABS"/*; do
    [[ -f "$hook" && ! -x "$hook" ]] || continue
    echo "→ chmod +x $(basename "$hook")"
    chmod +x "$hook"
done

cat <<EOF

✓ githooks installed: $REPO_ROOT → core.hooksPath = $HOOKS_DIR_REL

Active hooks:
$(ls -1 "$HOOKS_DIR_ABS" 2>/dev/null | sed 's/^/  · /')

Bypass options:
  · git commit --no-verify ...
  · AGENT_BRIDGE_SKIP_PRECOMMIT=1 git commit ...   (pre-commit only)
EOF
