#!/usr/bin/env bash
# Review a remote install shell script without executing it.
#
# This helper is intentionally a capture + static-review tool. It never pipes
# downloaded bytes into a shell and never runs the reviewed installer.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/review-remote-install.sh --url <commit-pinned raw GitHub URL> [options]
  scripts/review-remote-install.sh --local-file <path> [options]

Options:
  --output-dir <dir>          Review output directory. Default: mktemp dir.
  --expected-sha256 <sha>     Require the reviewed bytes to match this SHA-256.
  --max-bytes <n>             Refuse scripts larger than n bytes. Default: 262144.
  --allow-mutable-ref         Allow non-commit raw GitHub refs for review only.
  -h, --help                  Show this help.

The helper downloads or copies the script to a review file, records SHA-256,
runs syntax/static checks, and emits report.md with execute_remote_script_now=false.
It never executes the installer.
USAGE
}

die() {
  echo "error: $*" >&2
  exit 2
}

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    die "sha256sum or shasum is required"
  fi
}

url=""
local_file=""
output_dir=""
expected_sha256=""
max_bytes=262144
allow_mutable_ref=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      [[ $# -ge 2 ]] || die "--url requires a value"
      url="$2"
      shift 2
      ;;
    --local-file)
      [[ $# -ge 2 ]] || die "--local-file requires a value"
      local_file="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || die "--output-dir requires a value"
      output_dir="$2"
      shift 2
      ;;
    --expected-sha256)
      [[ $# -ge 2 ]] || die "--expected-sha256 requires a value"
      expected_sha256="$2"
      shift 2
      ;;
    --max-bytes)
      [[ $# -ge 2 ]] || die "--max-bytes requires a value"
      max_bytes="$2"
      [[ "$max_bytes" =~ ^[0-9]+$ ]] || die "--max-bytes must be numeric"
      shift 2
      ;;
    --allow-mutable-ref)
      allow_mutable_ref=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

if [[ -n "$url" && -n "$local_file" ]]; then
  die "use either --url or --local-file, not both"
fi
if [[ -z "$url" && -z "$local_file" ]]; then
  die "one of --url or --local-file is required"
fi
if [[ -n "$expected_sha256" && ! "$expected_sha256" =~ ^[0-9a-fA-F]{64}$ ]]; then
  die "--expected-sha256 must be 64 hex characters"
fi

owner=""
repo=""
ref=""
script_path_in_repo=""
source_mode="remote"

if [[ -n "$url" ]]; then
  [[ "$url" != *"..."* ]] || die "URL contains ellipsis; provide the complete raw GitHub URL"
  [[ "$url" != *"@"* ]] || die "URL must not contain embedded credentials"
  [[ "$url" != *"?"* && "$url" != *"#"* ]] || die "URL must not contain query strings or fragments"

  if [[ "$url" =~ ^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([0-9a-fA-F]{40})/(.+)$ ]]; then
    owner="${BASH_REMATCH[1]}"
    repo="${BASH_REMATCH[2]}"
    ref="${BASH_REMATCH[3]}"
    script_path_in_repo="${BASH_REMATCH[4]}"
  elif [[ "$allow_mutable_ref" -eq 1 && "$url" =~ ^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$ ]]; then
    owner="${BASH_REMATCH[1]}"
    repo="${BASH_REMATCH[2]}"
    ref="${BASH_REMATCH[3]}"
    script_path_in_repo="${BASH_REMATCH[4]}"
  else
    die "URL must be https://raw.githubusercontent.com/OWNER/REPO/40_HEX_COMMIT/path by default"
  fi
else
  source_mode="local"
  [[ -f "$local_file" ]] || die "local file not found: $local_file"
  owner="<local>"
  repo="<local>"
  ref="<local>"
  script_path_in_repo="$local_file"
fi

if [[ -z "$output_dir" ]]; then
  output_dir="$(mktemp -d "${TMPDIR:-/tmp}/ab-remote-install-review-XXXXXX")"
fi
mkdir -p "$output_dir"

review_script="$output_dir/install.sh"
hash_file="$output_dir/sha256.txt"
bashn_file="$output_dir/bash-n.txt"
shellcheck_file="$output_dir/shellcheck.txt"
risk_file="$output_dir/risk-scan.txt"
report_file="$output_dir/report.md"

if [[ "$source_mode" == "remote" ]]; then
  command -v curl >/dev/null 2>&1 || die "curl is required for --url"
  curl --fail --show-error --location --proto '=https' \
    --connect-timeout 10 --max-time 60 --max-filesize "$max_bytes" \
    --output "$review_script" "$url"
else
  cp "$local_file" "$review_script"
fi

bytes="$(wc -c < "$review_script" | tr -d '[:space:]')"
[[ "$bytes" =~ ^[0-9]+$ ]] || die "could not determine script size"
if (( bytes > max_bytes )); then
  die "script is ${bytes} bytes, exceeds --max-bytes ${max_bytes}"
fi

script_sha256="$(sha256_file "$review_script")"
printf '%s  install.sh\n' "$script_sha256" > "$hash_file"
if [[ -n "$expected_sha256" && "${script_sha256,,}" != "${expected_sha256,,}" ]]; then
  echo "expected: ${expected_sha256,,}" >> "$hash_file"
  echo "actual:   ${script_sha256,,}" >> "$hash_file"
  die "SHA-256 mismatch; see $hash_file"
fi

bashn_status=0
if bash -n "$review_script" > "$bashn_file" 2>&1; then
  echo "bash -n: pass" >> "$bashn_file"
else
  bashn_status=$?
  echo "bash -n: fail (${bashn_status})" >> "$bashn_file"
fi

shellcheck_status="not_available"
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck "$review_script" > "$shellcheck_file" 2>&1; then
    shellcheck_status="pass"
    echo "shellcheck: pass" >> "$shellcheck_file"
  else
    shellcheck_status="warn"
    echo "shellcheck: warn" >> "$shellcheck_file"
  fi
else
  echo "shellcheck: not_available" > "$shellcheck_file"
fi

risk_count=0
: > "$risk_file"
scan_pattern() {
  local label="$1"
  local pattern="$2"
  {
    echo "## ${label}"
    if grep -En "$pattern" "$review_script"; then
      risk_count=$((risk_count + 1))
    else
      echo "(none)"
    fi
    echo
  } >> "$risk_file"
}

scan_pattern "pipe_to_shell" '(curl|wget)[^|;]*\|[[:space:]]*(sudo[[:space:]]+)?(ba)?sh|source[[:space:]]+<\('
scan_pattern "network_fetch" '(^|[^[:alnum:]_])(curl|wget|git[[:space:]]+clone|gh[[:space:]]+repo[[:space:]]+clone)[^[:alnum:]_-]'
scan_pattern "package_install" '(^|[^[:alnum:]_])(apt(-get)?|dnf|yum|pacman|zypper|brew|pipx?|npm|pnpm|yarn|cargo)[[:space:]].*(install|add)'
scan_pattern "privilege_escalation" '(^|[^[:alnum:]_])(sudo|su|doas)[[:space:]]'
scan_pattern "service_changes" '(systemctl|launchctl|crontab|/etc/systemd|Library/LaunchAgents|cron\.d)'
scan_pattern "secrets_or_ssh" '(\.ssh|authorized_keys|id_rsa|TOKEN|PASSWORD|SECRET|CREDENTIAL|\.env)'
scan_pattern "destructive_or_sensitive_write" '(rm[[:space:]]+-rf|chmod[[:space:]]+777|chown[[:space:]]|tee[[:space:]].*(/etc|/usr|/opt|/var|HOME|~)|>[>]?(/[[:alnum:]]|~|\$HOME))'

cat > "$report_file" <<EOF
# Remote Install Script Review

schema: agent_bridge.remote_install_review_helper.v0

source_mode: ${source_mode}
source_url: ${url:-<local-file>}
owner: ${owner}
repo: ${repo}
ref: ${ref}
path: ${script_path_in_repo}
bytes: ${bytes}
sha256: ${script_sha256}

curl_pipe_shell_allowed: false
execute_remote_script_now: false
commit_pin_required: true
mutable_ref_allowed_for_review: $([[ "$allow_mutable_ref" -eq 1 ]] && echo true || echo false)

review_files:
- script: ${review_script}
- sha256: ${hash_file}
- bash_n: ${bashn_file}
- shellcheck: ${shellcheck_file}
- risk_scan: ${risk_file}

checks:
- bash_n_status: $([[ "$bashn_status" -eq 0 ]] && echo pass || echo fail)
- shellcheck_status: ${shellcheck_status}
- risk_sections_with_matches: ${risk_count}

decision:
- Do not execute this installer from the helper.
- Use this report as input to a source-specific review packet.
- Execution requires separate owner approval after static review.
EOF

echo "review_dir=$output_dir"
echo "report=$report_file"

if [[ "$bashn_status" -ne 0 ]]; then
  exit 1
fi
