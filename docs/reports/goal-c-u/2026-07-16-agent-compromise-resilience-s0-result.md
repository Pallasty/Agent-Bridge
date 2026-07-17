# Agent-Compromise Resilience S0 Result

Date: 2026-07-16

Status: `PASS / DIRECT_INTEGRATION_NO_GO / STATIC_BOUNDARY_EVIDENCE_ONLY / NO_RUNTIME_AUTHORITY`

## Decision

Retain `codex-redteam-mode` as a hostile control-plane research sample. Do not
install it into Agent-Bridge, import its hooks or prompts, or treat its approval
model as authority.

The frozen S0 evaluator passed all preregistered gates. This proves that the
standalone deterministic policy encoded by this experiment classifies the 34
frozen structured cases as intended and emits no execution or mutation
authority. It does **not** prove that the live Agent-Bridge runtime currently
routes every equivalent hostile input through this evaluator. The evaluator is
deliberately example-only and disconnected from MCP and runtime admission.

## Frozen Source

Protocol anchor:

```text
f2e3076b8c0b132db0789b48f8151ac11fa69760
```

Agent-Bridge base:

```text
08594b04fe9e23b11c70b3a5640c43ada9911a7b
```

Upstream sample:

```text
repository:    https://github.com/chAng-L19/codex-redteam-mode
main commit:   915747da34cf1dc016ae5bfdd7b5cede2677a5fc
stable tag:    v1.3.0
stable commit: 817b249da85807f981ee5a9eccc95202e20072c2
```

All nine upstream source hashes embedded in the corpus were recomputed from
the pinned checkout before the admitted run and matched exactly. No upstream
file was executed.

## S0 Result

| Metric | Result |
|---|---:|
| cases | 34 |
| hostile cases | 30 |
| safe controls | 4 |
| exact verdict matches | 34 |
| false permits | 0 |
| false blocks among inert-allow controls | 0 |
| authority violations | 0 |

Verdict distribution:

| Verdict | Count |
|---|---:|
| `blocked` | 25 |
| `pivot` | 3 |
| `review_only` | 4 |
| `allow_inert_read_only` | 2 |

One evidence-self-certification case is blocked instead of pivoted because it
also claims prompt authority; the earlier, stronger authority rule wins. The
remaining three self-certification cases pivot to external evidence.

Every case and the aggregate report emitted:

```text
may_execute_tool=false
may_write_memory=false
may_write_graph=false
may_change_retrieval=false
may_enable_runtime=false
may_rewrite_session=false
```

## Determinism And Artifact Identity

The evaluator ran twice from the protocol anchor. `cmp` reported no byte
difference.

| Artifact | SHA-256 |
|---|---|
| embedded corpus | `239d5ca7c823fdf8c946abb4d2563e51fc6732cc9dd9a40c8c57946715325849` |
| run 1 packet | `bc3b90397a2c04441db9ef3b5966ee44c81e829393c5e573493b51555b3c1ebc` |
| run 2 packet | `bc3b90397a2c04441db9ef3b5966ee44c81e829393c5e573493b51555b3c1ebc` |

The packets remained under `/tmp`; they contain no timestamp, credential,
machine-specific repository path, real target, or runtime observation.

## Read-Only Research Review

The deployed `research_cycle_plan` advisory tool was called with the source
anchors, falsifier, exact evidence summary, and reproducibility handle after
the admitted run. It returned zero blockers and classified the packet as ready
for human-readable review. Its own boundaries remained explicit:

```text
may_execute=false
may_write_memory=false
may_write_forum=false
may_change_runtime_policy=false
human_review_required=true
```

This advisory result is consistency evidence for the research process, not an
independent security review and not an action permit.

## Upstream Research Findings

Static inspection supports three different judgments:

| Proposed use | Value | Decision |
|---|---|---|
| direct AB installation or integration | negative | `NO_GO` |
| abstract architecture pattern catalog | moderate | `CONDITIONAL` |
| hostile agent-control-plane benchmark | high | `GO_WITH_STATIC_BOUNDARIES` |

Useful abstract patterns include a four-grade outcome vocabulary, explicit
boundary/pivot/evidence cards, separation of registry/scope/gate/executor
roles, and artifact-first progression. These can be re-derived under AB's
authority model without importing upstream code.

The unsafe or unproven elements are more important:

- current main includes changes described as removing authorization and
  treating work as pre-authorized;
- current configuration permits restricted actions and does not require scope
  for network activity;
- approval, session patching, adapter registration, and self-authored evidence
  remain inside the agent-controlled trust domain;
- inspected CI failures reflected tests expecting earlier safer defaults; a
  proposed test update changes assertions rather than supplying an independent
  effectiveness benchmark;
- no controlled benchmark was found that demonstrates improved red-team task
  effectiveness, lower false-block rate, or safe containment.

Therefore the project's strongest research contribution to AB is adversarial:
it supplies concrete examples of claims that an independent bridge must not
trust.

## AB Value And Limits

S0 validates the design direction: authorization, scope, provenance, evidence,
and runtime admission should remain independent dimensions, and hostile agent
claims should collapse to review, pivot, or block without changing state.

S0 does not validate the current live AB runtime against arbitrary compromised
agent traffic. It also does not cover arbitrary code execution, same-process
memory corruption, sandbox escape, covert channels, or malformed wire-level
MCP traffic. Those require different trust boundaries and test methods.

## Next Admissible Gate

The next useful step is an S1 design and mapping review, not runtime execution:

1. map each S0 attack category to the existing AB T6 scope, authority,
   provenance, evidence, and non-admission fields;
2. identify cases that already have a live boundary owner and cases that are
   only represented by this offline evaluator;
3. add malformed-schema and pairwise-composition mutations to a separately
   preregistered corpus;
4. require author review before connecting any case to an actual MCP dispatch,
   memory write, retrieval change, session mutation, or runtime-enable path.

S0 itself authorizes none of those actions. Deployment is neither required nor
permitted for this result.

## Verification

Passed locally:

```text
cargo test -p ab-bridge --no-default-features \
  --example agent_compromise_resilience_eval -- --nocapture
  4 passed; 0 failed

pre-commit cargo check -p ab-bridge --all-targets
  passed with pre-existing warnings

python3 -m json.tool (corpus)
rustfmt --edition 2021 --check (evaluator)
git diff --check
source SHA-256 recomputation for nine pinned upstream files
two cargo-run packets compared byte-for-byte
```
