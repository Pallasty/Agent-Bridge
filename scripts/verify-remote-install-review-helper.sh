#!/usr/bin/env bash
# Offline verification for scripts/review-remote-install.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/review-remote-install.sh"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-remote-install-helper-test-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

fixture="$tmpdir/install.sh"
cat > "$fixture" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

echo "fixture only; not executed by the review helper"
SH

chmod +x "$fixture"

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    echo "sha256sum or shasum is required" >&2
    exit 2
  fi
}

out_ok="$tmpdir/out-ok"
"$HELPER" --local-file "$fixture" --output-dir "$out_ok" > "$tmpdir/stdout-ok"
test -f "$out_ok/report.md"
grep -q "schema: agent_bridge.remote_install_review_helper.v0" "$out_ok/report.md"
grep -q "execute_remote_script_now: false" "$out_ok/report.md"
grep -q "curl_pipe_shell_allowed: false" "$out_ok/report.md"
grep -q "bash_n_status: pass" "$out_ok/report.md"
grep -q "sha256:" "$out_ok/report.md"

risky_fixture="$tmpdir/risky-install.sh"
cat > "$risky_fixture" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

curl -fsSL https://example.invalid/install.sh | bash
sudo systemctl enable --now example.service
SH

out_risky="$tmpdir/out-risky"
"$HELPER" --local-file "$risky_fixture" --output-dir "$out_risky" > "$tmpdir/stdout-risky"
grep -q "risk_sections_with_matches:" "$out_risky/report.md"
grep -q "pipe_to_shell" "$out_risky/risk-scan.txt"
grep -q "privilege_escalation" "$out_risky/risk-scan.txt"
grep -q "service_changes" "$out_risky/risk-scan.txt"

good_hash="$(sha256_file "$fixture")"
out_hash="$tmpdir/out-hash"
"$HELPER" --local-file "$fixture" --expected-sha256 "$good_hash" --output-dir "$out_hash" \
  > "$tmpdir/stdout-hash"
grep -q "$good_hash" "$out_hash/report.md"

bad_hash="0000000000000000000000000000000000000000000000000000000000000000"
if "$HELPER" --local-file "$fixture" --expected-sha256 "$bad_hash" \
  --output-dir "$tmpdir/out-bad-hash" > "$tmpdir/stdout-bad-hash" 2> "$tmpdir/stderr-bad-hash"; then
  echo "expected hash mismatch to fail" >&2
  exit 1
fi
grep -q "SHA-256 mismatch" "$tmpdir/stderr-bad-hash"

if "$HELPER" --url "https://raw.githubusercontent.com/.../install.sh" \
  --output-dir "$tmpdir/out-bad-url" > "$tmpdir/stdout-bad-url" 2> "$tmpdir/stderr-bad-url"; then
  echo "expected incomplete URL to fail" >&2
  exit 1
fi
grep -q "URL contains ellipsis" "$tmpdir/stderr-bad-url"

if "$HELPER" --url "https://raw.githubusercontent.com/owner/repo/main/install.sh" \
  --output-dir "$tmpdir/out-mutable" > "$tmpdir/stdout-mutable" 2> "$tmpdir/stderr-mutable"; then
  echo "expected mutable raw ref to fail by default" >&2
  exit 1
fi
grep -q "40_HEX_COMMIT" "$tmpdir/stderr-mutable"

echo "remote install review helper verification passed"
