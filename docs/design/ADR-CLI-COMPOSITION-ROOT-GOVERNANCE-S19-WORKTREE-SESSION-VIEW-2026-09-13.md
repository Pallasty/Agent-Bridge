# S19 WorktreeSession planning and result presentation

## Source and purpose

The owner requested the next governance stage after S18 on 2026-09-13.
Both SSH master refs were fetched and equal to
`7fba67a8b006bac4fe59b5e74a260eaebc17c77b`; baseline main.rs has 22,070 lines.

WorktreeSession is an existing single-domain CLI adapter. Its deterministic
name/branch/path construction and porcelain parsing remain interleaved with
repository discovery, directory creation and Git process execution. Extracting
those two value boundaries makes the root's effect sequence explicit and gives
the previously uncharacterized textual contract a focused regression surface.

## Boundary

Create binary-private cli::worktree_session_view with:

- plan_new_session(&Path, Option<&str>, u64) -> SessionPlan { branch, path };
- render_session_rows(&[u8]) -> i32, consuming completed Git stdout, preserving
  lossy decoding, parsing/printing order and the original default count type.

The root retains environment override/repository discovery, SystemTime and its
zero fallback, mkdir, base selection, plan stderr, Git invocation and status
handling, final success stderr/stdout, and the no-session diagnostic. The module
receives no environment, clock, filesystem reader, Git runner or mutable state.
No whole command family, CLI declarations or cross-domain dispatch moves.

## Frozen contracts

- AGENT_BRIDGE_REPO takes precedence over Git discovery. Keep the existing
  lossy/trim behavior for discovered repository paths and Path::join semantics.
- Name cleaning preserves ASCII letters/digits, '-' and '_'; every other
  Unicode scalar becomes one '-'. Only None/empty string becomes 'anon'.
  Do not trim, collapse characters, normalize paths or add conflict retries.
- Preserve repo discovery -> clock -> plan -> mkdir -> plan stderr -> Git add
  -> success stderr -> final stdout path. mkdir failure emits no plan, while
  Git failure may retain the newly created parent directory. Preserve all
  argument boundaries, errors, whitespace and Git stdout/stderr routing.
- List preserves input order, duplicates and the exact substring filter
  '/.worktrees/session-'. Keep empty-line block delimiters, last field wins,
  unknown-line handling, first eight HEAD characters, unparsed branch/path
  strings, detached/missing fields and trailing-block flush.
- No match emits only the existing root-owned stderr diagnostic. Git failure
  is handled before parsing or rendering any captured stdout.

## Preregistered acceptance

1. Extract exact baseline blocks from the source commit into standalone probes;
   compare fixed plans and raw porcelain bytes against the actual candidate
   module. Include malformed/Unicode/lossy cases and an output negative control.
2. Compare isolated baseline/candidate CLI help, discovery, list, new and error
   paths using a controlled Git executable; record exact argv and effects.
   Use local temporary Git repositories to verify actual refs, worktrees,
   explicit base selection and failure behavior. Generated slug timestamps
   must be validated against each call before replacing only that exact slug
   in comparisons. Do not claim Git index/object file byte equivalence.
3. Keep all owner credentials/configuration and Git repositories outside the
   fixture. Use a real empty credential file plus explicit HOME/XDG and Git
   config isolation; no remote Git operation is part of CLI tests.
4. Add focused root-boundary tests; run cargo check -p ab-bridge --all-targets
   --quiet, scoped rustfmt/diff checks and staged/committed governance admission.
5. Record bound source/verification evidence and a fresh receipt; synchronize
   the accepted commit to both SSH remotes using [skip ci] and GitLab ci.skip.

## Verification and outcome

Both blocks are extracted; main.rs now has 22,024 lines, 46 fewer. Whole-file
comparison with each old block/new call replaced by the same marker proves
all other bytes unchanged. Independent source review confirms the boundary,
including unchanged main, real_main, build_hub and CLI declarations.

The fixed probes pass 64/64 cases: 22 plans and 42 raw listing inputs. An extra
output negative control is rejected. The CLI harness passes 34/34 cases:
22 compare unmodified CLI bytes and 12 validate and normalize only the generated
slug. The backend split is 27 controlled Git cases and seven real local Git
cases, covering refs, worktrees, explicit base selection, checkout content and
failure effects. The original repository and owner state are never test inputs.

Three boundary tests, 20 Git/hook tests, 3 positive/7 negative governance
controls, all-targets cargo check, scoped rustfmt and diff checks pass. The
source/module and both harness hashes remain stable during verification.
This accepts the original behavior; it does not add a same-second collision
retry or claim cross-stream wall-clock scheduling or Git database byte parity.

Reproduce after building and preserving baseline/candidate executables with
the same Cargo configuration and a target directory on real disk:

```sh
python3 scripts/eval/worktree_session_view_parity.py --output-dir <report-dir>/view
python3 scripts/eval/worktree_session_cli_parity.py --baseline <baseline-bin> --candidate <candidate-bin> --output <report-dir>/cli-parity.json
cargo test -p ab-bridge --test cli_worktree_session_s19_extraction
cargo check -p ab-bridge --all-targets --quiet
bash scripts/check-cli-composition-root-governance.sh 7fba67a8b006bac4fe59b5e74a260eaebc17c77b HEAD
```

The view probe takes --deps-dir for an alternate compiled serde_json dependency
directory and extracts its baseline from the recorded source commit. Durable
evidence is in `docs/reports/main-rs-governance/2026-09-13-s19-verification.json`
and `docs/design/evidence/cli-composition-root-governance/2026-09-13-s19-worktree-session-view.json`.
S19 is complete within this planning/presentation boundary.

## Rollback

Revert the S19 extraction to restore the two inline blocks. There is no schema,
configuration, runtime or persistent-state migration. Test worktrees exist only
inside disposable fixture repositories. S14–S18 decisions remain unchanged.
