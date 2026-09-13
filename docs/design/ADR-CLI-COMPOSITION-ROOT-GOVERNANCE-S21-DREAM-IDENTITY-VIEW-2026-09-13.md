# S21 Dream identity section presentation

## Source and purpose

The owner requested the next main.rs governance stage after S20 on 2026-09-13.
Both fetched SSH master refs equal
`02141eeab7a31ca55b2bc91584848747ea5e1f4e`; main.rs has 21,952 lines.

The completed `IdentityWindow` pair already separates query work from the
identity report sections. Move `pct_delta` and `print_identity_section` to
binary-private `cli::dream_identity_view` to give that presentation boundary
an independent fixed-input characterization surface.

## Boundary and frozen behavior

Move only the two helper bodies and qualify the sole section-rendering call.
Keep `pct_delta` private; expose the section renderer only within the binary.
Reuse the existing `cli::dream::short_key` without changing it. The new module
may print completed sections but receives no Store, clock, filesystem access,
configuration, process runner or runtime capability.

`run_dream_identity` retains the days gate, SystemTime, window arithmetic,
default DB path, open, current query then prior query and their exact error
contexts. The JSON branch, text title, DB line, blank lines and final return
remain at root. Preserve the existing statement and print order. The existing
S11 `cli::dream` no-output contract stays intact; this separately characterized
section renderer does not reopen its executors or the S17 retained adapters.

Preserve zero-prior delta wording, signed percentage width/precision, original
f64 arithmetic and zero-total ok rates. Top tools preserve current input order,
show at most eight, use original Unicode short_key handling, and take the last
matching prior count. Forum kinds use a sorted union, the first matching current
count and the last matching prior count; render when either side is nonempty.
Preserve empty names, duplicates, whitespace, rounding and every newline.
Do not redesign the output or sanitize already completed values.

## Preregistered acceptance

1. Extract both original helpers from the source base into a probe using the
   actual ab_store::IdentityWindow and original short_key implementation.
   Compare fixed-input stdout/stderr/exit with the actual candidate module,
   including zero/growth/decline, large counts, ordering, duplicates, eight-row
   cap, Unicode/truncation and forum-average boundaries. Detect an output
   negative control; bind source, harness and dependency hashes.
2. Characterize real baseline CLI behavior before candidate comparison. Use
   fully isolated environment, an actual empty credential file and disposable
   SQLite fixtures for help, defaults, days errors, empty/populated text/JSON
   and open/query failures. Validate invocation time and window relationships
   before normalizing only JSON window endpoints. Compare business rows rather
   than SQLite file bytes. No owner state is a fixture.
3. Record an ownership test failure before movement, then focused boundary
   tests and source-byte comparison proving all bytes outside the helpers and
   qualified call are unchanged. Keep the Store type and existing Dream module
   unchanged. Run the relevant adjacent Dream ownership tests, all-targets
   Cargo check, scoped rustfmt, diff and governance admission checks.
4. Bind a fresh receipt and verification record, then synchronize the accepted
   commit to both SSH remotes with [skip ci] and GitLab ci.skip.

## Verification and outcome

Both helper bodies are byte-identical after extraction. The section function
gains binary-private visibility and signature line wrapping only. All root
bytes outside the two removed helpers and qualified call are unchanged,
including main, real_main and build_hub. main.rs now has 21,848 lines, down 104.

The baseline-only probe first rendered all 44 fixed windows successfully; the
candidate then matched all 44 exit/stdout/stderr results. The output negative
control was detected. Cases cover the eight-tool cap, duplicates, Unicode,
large integer/f64 boundaries, signed zero, NaN and infinities in completed
values, forum union ordering and average rounding. Source and dependency
hashes stayed unchanged during both runs.

The CLI baseline characterization passed 30/30 before candidate comparison.
The comparison also passed 30/30: 24 exact CLI cases and six JSON cases with
only the four validated window endpoints normalized. Four named fixture
business tables retain their rows. Filesystem checks permit the existing empty
private init.lock; this is not a claim of SQLite byte equivalence or absence
of every internal Store write. Both binary and harness hashes stayed stable.

All three new boundary tests failed at their expected missing owner/call
before movement, then passed after extraction. Existing S11, S12 and S13
ownership tests each passed, for six focused Rust tests in total. All-targets
Cargo check, 20 governance unit tests, three positive/seven negative schema
checks, scoped rustfmt and diff checks passed. Evidence is bound in the
[verification record](../reports/main-rs-governance/2026-09-13-s21-verification.json)
and [governance receipt](evidence/cli-composition-root-governance/2026-09-13-s21-dream-identity-view.json).

Reproduce after preserving a source-base executable as agent-bridge-baseline
in the analysis directory:

```sh
export CARGO_TARGET_DIR=/Data/ab-main-rs-governance-target
export CARGO_BUILD_JOBS=4
cargo build -p ab-bridge --bin agent-bridge
cargo test -p ab-bridge --test cli_dream_identity_s21_extraction --test cli_dream_html_extraction --test cli_agent_md_drift_extraction --test cli_skill_retro_extraction
cargo check -p ab-bridge --all-targets --quiet
python3 scripts/eval/dream_identity_view_parity.py \
  --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s21-20260913/view
python3 scripts/eval/dream_identity_cli_parity.py \
  --baseline /Data/CascadeProjects/.analysis-reports/main-rs-governance-s21-20260913/agent-bridge-baseline \
  --candidate /Data/ab-main-rs-governance-target/debug/agent-bridge \
  --output /Data/CascadeProjects/.analysis-reports/main-rs-governance-s21-20260913/cli-parity.json
bash scripts/check-cli-composition-root-governance.sh \
  02141eeab7a31ca55b2bc91584848747ea5e1f4e HEAD
```

Both comparison scripts also support --baseline-only for independent baseline
characterization. The view probe accepts --deps-dir for an alternate existing
Cargo dependency directory and uses the recorded source-base commit.

## Rollback

Revert S21 to restore both inline helpers and their original call. No data,
schema or configuration migration is required.
