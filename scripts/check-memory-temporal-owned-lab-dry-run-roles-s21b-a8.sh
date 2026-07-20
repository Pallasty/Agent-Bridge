#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail
umask 077
PATH=/usr/bin:/bin:/home/pallasting/.cargo/bin
export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$(mktemp -d)"
trap 'rm -f "$output_dir"/*.json; rmdir "$output_dir"' EXIT
cd "$root"
CARGO_BUILD_JOBS=1 cargo test --locked --offline -p ab-owned-lab-role-artifacts --no-default-features -j 1 >/dev/null
CARGO_BUILD_JOBS=1 cargo build --locked --offline -p ab-owned-lab-role-artifacts --no-default-features --bins -j 1 >/dev/null
for role in controller observer runner validator; do
  "$root/target/debug/ab-owned-lab-$role" --dry-run-protocol-v1 >"$output_dir/$role.json"
  if "$root/target/debug/ab-owned-lab-$role" --unsupported >/dev/null 2>/dev/null; then
    printf 'unsupported argument accepted by %s\n' "$role" >&2
    exit 1
  else
    test "$?" -eq 64
  fi
done
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_dry_run_roles_s21b_a8.py" --output-dir "$output_dir"
