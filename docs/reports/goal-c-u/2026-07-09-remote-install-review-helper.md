# Remote Install Review Helper

Date: 2026-07-09

Source base commit: `43de22e9`

Run type: no-execution helper implementation packet

Parent safety packet:

- `docs/reports/goal-c-u/2026-07-09-remote-install-script-safety-packet.md`

AB planning anchors:

- Durable memory key: `remote_install_review_helper_20260709`
- Forum thread: `design#120`, post `2959`

## Verdict

Implement the safety gate as a local review helper, not as an installer.

The helper captures a remote or local installer script into a review directory,
records its SHA-256, runs syntax/static checks, scans for high-risk patterns,
and emits a report. It never pipes the script into a shell and never executes
the reviewed installer.

## Landed Files

```text
scripts/review-remote-install.sh
scripts/verify-remote-install-review-helper.sh
docs/reports/goal-c-u/2026-07-09-remote-install-review-helper.md
```

## Helper Contract

```yaml
schema: agent_bridge.remote_install_review_helper.v0
curl_pipe_shell_allowed: false
execute_remote_script_now: false
commit_pin_required: true
default_allows_mutable_ref: false
offline_fixture_verification: true
remote_installer_execution: false
```

Supported modes:

- `--url <url>`: accepts `https://raw.githubusercontent.com/OWNER/REPO/40_HEX_COMMIT/path`
  by default.
- `--local-file <path>`: reviews a file already captured elsewhere, used by
  tests and offline review.

Output files:

- `install.sh`: captured bytes under review.
- `sha256.txt`: hash of captured bytes.
- `bash-n.txt`: shell syntax check output.
- `shellcheck.txt`: shellcheck output when available, otherwise a
  `not_available` marker.
- `risk-scan.txt`: grouped grep findings for risky behavior.
- `report.md`: review summary with `execute_remote_script_now: false`.

## Rejection Behavior

The helper rejects:

- URLs containing `...`;
- URLs with embedded credentials, query strings, or fragments;
- non-raw GitHub URLs in `--url` mode;
- mutable refs by default;
- SHA-256 mismatches;
- files above the configured size cap;
- shell syntax failures.

Mutable refs can only be reviewed with `--allow-mutable-ref`; this does not
authorize execution and is meant for triage, not approval.

## Static Risk Scan

The helper records matches for:

- pipe-to-shell patterns;
- network fetches;
- package installation;
- privilege escalation;
- service manager changes;
- secret or SSH paths;
- destructive or sensitive writes.

The scan is intentionally conservative. A clean scan is not an approval to run;
it only reduces the work needed for the source-specific review packet.

## Verification

Pre-registered verification:

```bash
bash -n scripts/review-remote-install.sh scripts/verify-remote-install-review-helper.sh
scripts/verify-remote-install-review-helper.sh
git diff --check
rg -n "agent_bridge.remote_install_review_helper.v0|execute_remote_script_now: false|curl_pipe_shell_allowed: false|commit_pin_required: true" scripts docs/reports/goal-c-u/2026-07-09-remote-install-review-helper.md
```

The verifier is offline:

- uses a local fixture only;
- confirms the report schema and blocked execution flags;
- confirms correct SHA-256 succeeds;
- confirms bad SHA-256 fails;
- confirms incomplete URL fails;
- confirms mutable raw refs fail by default.

## Belief Clarity Check

```yaml
belief_clarity_check:
  schema: agent_bridge.memory_belief_clarity_diagnostic.v0
  anchor_question: "Based on current memory, what is current task progress and what information is still needed?"
  progress_known:
    - "The safety gate exists as a docs-only packet."
    - "The helper now makes offline capture/hash/static review reproducible."
    - "The verifier proves incomplete URLs and mutable raw refs fail by default."
  information_missing:
    - "No source-specific remote installer URL has been reviewed yet."
    - "No sandbox execution plan has been approved for any installer."
    - "No owner approval exists for executing any reviewed installer."
  blockers:
    - "Do not use helper output as run approval."
    - "Do not review mutable refs as approval candidates."
    - "Do not execute downloaded installer code from this helper."
  uncertainty_markers:
    - "Static grep scans are conservative and can miss shell-obfuscated behavior."
    - "shellcheck is optional and may be unavailable on some hosts."
  premature_certainty_risk: low
  next_safe_surface: "source_specific_remote_install_review_packet"
  promotion_allowed: false
  may_write_memory_now: false
  may_change_retrieval_order_now: false
```

## Decision

Use `scripts/review-remote-install.sh` as the first local gate for future raw
GitHub installer reviews.

Do not execute any remote installer in this slice. A future full URL still
requires a source-specific review packet and explicit owner approval before
any sandboxed execution.
