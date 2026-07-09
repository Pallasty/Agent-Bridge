# Remote Install Script Safety Packet

Date: 2026-07-09

Source base commit: `104923cf`

Run type: docs-only supply-chain safety packet

Input pattern:

```bash
curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash
```

Safety classification:

```yaml
schema: agent_bridge.remote_install_script_safety.v0
runtime_authority: none
curl_pipe_shell_allowed: false
execute_remote_script_now: false
requires_full_url: true
requires_commit_pin: true
requires_offline_capture: true
requires_hash_verification: true
requires_static_review: true
requires_sandbox_dry_run: true
requires_owner_approval: true
promotion_allowed: false
```

AB planning anchors:

- Durable memory key: `remote_install_script_safety_packet_20260709`
- Forum thread: `design#120`, post `2957`

Local source anchors:

- `docs/design/EXTERNAL_SKILL_INTAKE_MINICPM5_SPIKE_2026_05_26.md`
- `README.md`
- `scripts/wrapper/install.sh`
- `scripts/launchd/install.sh`
- `scripts/systemd/install.sh`

External source anchors:

- curl man page: https://curl.se/docs/manpage.html
- Bash reference manual: https://www.gnu.org/software/bash/manual/bash.html
- GitHub repository contents API:
  https://docs.github.com/en/rest/repos/contents?apiVersion=2026-03-10

## Verdict

Do not run the command as written.

The URL is incomplete, so the script cannot be attributed, pinned, inspected,
or hashed. Even with a complete URL, piping a remote `install.sh` directly into
`bash` is a high-risk supply-chain intake pattern because the downloaded bytes
become shell input immediately.

AB should support a review workflow for this pattern, not direct execution.

## Boundary

This packet:

- does not fetch or execute the incomplete raw URL;
- does not guess the missing repository/path;
- does not modify local installer scripts;
- does not add a runtime install feature;
- does not change skill, package, bootstrap, or deployment behavior;
- does not bless `curl | bash` as an AB-supported install path.

## What The Command Actually Means

The command has two separate parts:

```bash
curl -fsSL URL
```

downloads bytes from a URL and writes them to standard output unless told
otherwise.

```bash
... | bash
```

feeds those bytes into a shell process. Bash then interprets shell syntax from
that input.

The curl flags improve transfer ergonomics, not trust:

| Flag | Useful behavior | Trust boundary |
| --- | --- | --- |
| `-f` / `--fail` | Fail on HTTP errors instead of printing an error page as body | Does not authenticate the script author |
| `-s` / `--silent` | Hides progress output | Can reduce visibility while running |
| `-S` / `--show-error` | Shows errors when silent mode is used | Does not inspect content |
| `-L` / `--location` | Follows redirects | Can execute bytes after a redirect target changes |

The pipe removes the review checkpoint between download and execution.

## Local AB Context

AB already has a safer pattern:

- local checked-in installer path;
- explicit shell script in the repository;
- `set -euo pipefail`;
- explicit install target paths;
- `--dry-run`, `--uninstall`, `--once`, `--no-daemons`, or OS guards where
  appropriate;
- failure before mutation when templates or platform assumptions are wrong.

Examples:

| Script | Guardrail observed |
| --- | --- |
| `scripts/wrapper/install.sh` | `--dry-run`, `--uninstall`, idempotent wrapper detection, explicit install path |
| `scripts/launchd/install.sh` | macOS-only guard, `--dry-run`, source existence checks, plist lint |
| `scripts/systemd/install.sh` | `--dry-run`, `--once`, `--no-daemons`, explicit unit list |

AB also already marks `curl ... | sh` as a warning in external skill intake:

```text
lint:warn:1 for `curl ... | sh`
```

That existing classification should generalize to raw GitHub installer scripts.

## Required Review Gate

Any future request to evaluate a full command of this form must satisfy this
gate before execution is even considered:

```yaml
remote_install_review_gate:
  schema: agent_bridge.remote_install_script_safety.v0
  full_url_present: true
  raw_url_uses_immutable_ref: true
  repository_identity_verified: true
  license_reviewed: true
  script_downloaded_to_file: true
  script_sha256_recorded: true
  static_review_completed: true
  network_writes_identified: true
  filesystem_writes_identified: true
  privilege_escalation_identified: true
  shell_options_identified: true
  uninstall_or_rollback_path_identified: true
  dry_run_or_noop_mode_identified: true
  sandbox_plan_defined: true
  owner_approval_recorded: true
  execute_remote_script_now: false
```

Immediate rejection criteria:

- URL is incomplete or uses an ellipsis.
- URL uses a mutable branch name such as `main` or `master` without a resolved
  commit SHA.
- Script requires `sudo` before inspection.
- Script downloads and executes additional scripts without pinning.
- Script writes shell startup files, service units, package repositories, SSH
  keys, credentials, or daemon state without an explicit rollback path.
- Script masks errors or ignores command failures around writes.
- Script has no dry-run/no-op mode and cannot be sandboxed.

## Safe Replacement Workflow

Use this workflow instead of direct pipe execution:

```bash
# 1. Use a full immutable URL, preferably commit-SHA pinned.
URL='https://raw.githubusercontent.com/OWNER/REPO/COMMIT/path/install.sh'

# 2. Download to a review file, not to bash.
tmp="$(mktemp -d)"
curl --fail --show-error --location --output "$tmp/install.sh" "$URL"

# 3. Record hash and inspect before running.
sha256sum "$tmp/install.sh"
sed -n '1,240p' "$tmp/install.sh"

# 4. Static checks. Use available tools; do not treat warnings as cosmetic.
bash -n "$tmp/install.sh"
shellcheck "$tmp/install.sh" 2>/dev/null || true

# 5. Only after review, run the script in an isolated environment or dry-run.
bash "$tmp/install.sh" --help
```

If the script lacks `--help`, `--dry-run`, or a clear install target, keep it
blocked.

## Source-Specific Inspection Checklist

When a full URL is provided, produce a separate packet with:

| Field | Required evidence |
| --- | --- |
| `owner/repo/path` | Parsed from the raw URL |
| `ref` | Commit SHA or immutable release artifact |
| `resolved_commit` | `git ls-remote` or GitHub API evidence |
| `license` | Repository license or explicit unknown |
| `script_hash` | SHA-256 of downloaded bytes |
| `line_count` | Bounded size; large scripts need stronger review |
| `shell_flags` | `set -euo pipefail` or absence |
| `network_calls` | `curl`, `wget`, package manager, git clone, model download |
| `filesystem_writes` | Paths touched, especially home, config, service dirs |
| `privilege_escalation` | `sudo`, `su`, package manager writes |
| `service_changes` | launchd/systemd/cron/profile edits |
| `secrets_handling` | env vars, tokens, key files, credential prompts |
| `rollback` | uninstall path or manual cleanup plan |
| `dry_run` | documented no-write mode or blocked |

## Belief Clarity Check

```yaml
belief_clarity_check:
  schema: agent_bridge.memory_belief_clarity_diagnostic.v0
  anchor_question: "Based on current memory, what is current task progress and what information is still needed?"
  progress_known:
    - "AB already treats curl-pipe-shell as at least lint warning in external skill intake."
    - "AB's own installer pattern favors local checked-in scripts with dry-run and guardrails."
    - "The supplied command is incomplete and cannot be source-specifically audited."
    - "Official curl/Bash docs confirm the command is download-to-stdout plus shell execution behavior."
  information_missing:
    - "Full raw.githubusercontent.com URL."
    - "Repository owner, repo, path, and immutable ref."
    - "Downloaded script bytes and SHA-256."
    - "Line-by-line static review of writes, network calls, and privilege changes."
  blockers:
    - "Do not execute incomplete raw URL."
    - "Do not execute mutable-branch raw installer before commit pin and review."
    - "Do not ingest installer as trusted AB pattern without owner approval."
  uncertainty_markers:
    - "No source-specific script body was available in this prompt."
    - "The command may refer to any GitHub repository; risk cannot be narrowed yet."
  premature_certainty_risk: low
  next_safe_surface: "source_specific_remote_install_review_packet"
  promotion_allowed: false
  may_write_memory_now: false
  may_change_retrieval_order_now: false
```

## Decision

Adopt `agent_bridge.remote_install_script_safety.v0` as a report convention for
future raw GitHub installer reviews.

The command as provided remains blocked:

```yaml
curl_pipe_shell_allowed: false
execute_remote_script_now: false
requires_full_url: true
requires_commit_pin: true
```

Next safe step: if a complete URL is provided, create a
`source_specific_remote_install_review_packet` that downloads the script to a
file, records its hash, performs static review, and keeps execution disabled
until owner approval.

## Verification Command

```bash
git diff --check && rg -n "agent_bridge.remote_install_script_safety.v0|curl_pipe_shell_allowed: false|requires_full_url: true|requires_commit_pin: true|execute_remote_script_now: false" docs/reports/goal-c-u/2026-07-09-remote-install-script-safety-packet.md
```
