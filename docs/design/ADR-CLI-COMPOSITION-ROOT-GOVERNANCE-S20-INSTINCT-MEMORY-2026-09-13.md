# S20 Instinct memory-record preparation

## Source and purpose

The owner requested the next main.rs governance stage after S19 on 2026-09-13.
Both fetched SSH master refs equal
`dd04c98bc58882195392f8649d88808863c77ed1`; baseline main.rs has 22,024 lines.

memory_record_from_instinct_plan currently combines seven fields of pure
validation/normalization, clock acquisition, and passive MemoryRecord
construction. Its single caller already owns the write-admission, database and
receipt sequence. Extracting the value transformation makes those different
responsibilities testable without widening the Instinct domain API.

## Boundary and frozen behavior

New binary-private cli::instinct_memory owns:

- prepare_memory_record(&Value) -> Result<PreparedMemoryRecord>, with seven
  private prepared fields and no clock, filesystem, Store or runner;
- PreparedMemoryRecord::into_record(self, now: i64) -> ab_store::MemoryRecord,
  consuming those fields with a timestamp already acquired by the root.

The existing root helper and its sole call site remain. The helper first
propagates preparation failure, then reads SystemTime using the original
duration/as_secs/as-i64/zero-fallback expression, then constructs the record.
The write gate, error context, path selection, SQLite open/save, receipt and
presentation all remain at their existing positions. Preview never calls this
adapter. Successful preparation is not permission to write memory.

Preserve key -> kind -> content error ordering and exact messages. Strings use
str::trim; no kind whitelist is introduced. tags/related_keys ignore non-string
array items and empty trimmed values, preserving order and duplicates; wrong
container types become empty. scope only accepts a nonempty trimmed string.
importance uses as_f64, default 0.5, then clamp to [0,1]. Do not replace this
contract with MemoryRecord deserialization or the domain's draft-plan builder.

created_at and updated_at receive the supplied time; last_accessed_at and
access_count are zero, status is active, trigger_pattern and superseded_by are
None. Input lifecycle fields are ignored. Record assembly and its active-status
allocation remain after the clock read.

## Preregistered acceptance

1. Extract the exact old root helper from the source commit and the actual new
   root wrapper/module into probes using the real ab_store::MemoryRecord type.
   Replace only the exact clock expression with a counted fixed clock in both
   probes. Compare complete records (including omitted-None fields and f64 bit
   patterns), exact errors, and zero clock reads on errors / one on success.
2. Cover required-field priority, scalar/wrong inputs, Unicode whitespace,
   arbitrary kind, mixed/duplicate arrays, scope/default/importance boundaries,
   ignored lifecycle input and zero/negative/large timestamps. Include a
   negative control and bind source/harness hashes before and after execution.
3. Reuse the existing 79-case isolated Instinct CLI suite. Its write effects
   support gate/save/receipt behavior, not adapter timestamp correctness:
   SqliteStore independently obtains the timestamps it persists.
4. Adapt the existing S18 boundary test to follow the new private module while
   preserving its gate/open/save/receipt/render checks. Add focused conversion
   and authority tests; run cargo check -p ab-bridge --all-targets --quiet,
   scoped rustfmt/diff checks and staged/committed governance admission.
5. Bind a fresh receipt and verification record, then synchronize the accepted
   commit to both SSH remotes with [skip ci] and GitLab ci.skip.

No runtime feature, new memory-write authority or deployment is included.

## Verification and outcome

main.rs now has 21,952 lines, down 72 from the source base. Everything outside
memory_record_from_instinct_plan is byte-identical, including the complete
MemoryWrite arm. The original clock expression is also byte-identical.

The actual-record probe passed all 61 cases: 20 validation failures read the
clock zero times and 41 successful conversions read it once. Complete records,
importance bit patterns and exact error chains match the baseline. All three
negative controls (clock, field and error mutations) were detected. Source and
dependency hashes stayed unchanged during the run. The clock-expression
substitution tests call order and supplied-time propagation; it does not execute
the real SystemTime fallback path.

The unchanged Instinct CLI harness passed all 79 cases, including denied writes,
successful memory/receipt persistence and receipt failure after memory save.
Its database checks cover business effects; SqliteStore uses its own clock, so
adapter timestamp parity is established by the direct record probe above.

The four S18 and three S20 Rust tests passed, as did the all-target Cargo check,
20 governance unit tests, three positive and seven negative schema self-tests,
scoped rustfmt and diff checks. The durable
[verification record](../reports/main-rs-governance/2026-09-13-s20-verification.json)
binds the source, scripts, binaries, logs and case results. The
[governance receipt](evidence/cli-composition-root-governance/2026-09-13-s20-instinct-memory.json)
classifies the extracted transformation and the root's retained clock/effect
boundary and records evidence for all six contracts.

Reproduce from this worktree, retaining an executable built from the source base
as `agent-bridge-baseline` in the analysis directory:

```sh
export CARGO_TARGET_DIR=/Data/ab-main-rs-governance-target
export CARGO_BUILD_JOBS=4
cargo build -p ab-bridge --bin agent-bridge
cargo test -p ab-bridge --test cli_instinct_s18_extraction --test cli_instinct_s20_extraction
cargo check -p ab-bridge --all-targets --quiet
python3 scripts/eval/instinct_memory_record_parity.py \
  --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s20-20260913/record
python3 scripts/eval/instinct_cli_parity.py \
  --baseline /Data/CascadeProjects/.analysis-reports/main-rs-governance-s20-20260913/agent-bridge-baseline \
  --candidate /Data/ab-main-rs-governance-target/debug/agent-bridge \
  --output /Data/CascadeProjects/.analysis-reports/main-rs-governance-s20-20260913/cli-parity.json
python3 -m unittest discover -s tests -p test_cli_composition_root_governance.py
python3 scripts/eval/cli_composition_root_governance.py validate \
  --base dd04c98bc58882195392f8649d88808863c77ed1 --head HEAD
```

## Rollback

Revert S20 to restore the original inline helper. There is no data, schema or
configuration migration. Earlier S14–S19 code and governance decisions remain.
