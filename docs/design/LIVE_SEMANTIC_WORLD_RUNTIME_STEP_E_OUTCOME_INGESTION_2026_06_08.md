# Live Semantic World Runtime - Step E Outcome Ingestion Policy

**2026-06-08 - role: learning-boundary design**

Parent documents:
- [Live Semantic World Runtime v1 Requirements](LIVE_SEMANTIC_WORLD_RUNTIME_REQUIREMENTS_V1_2026_06_06.md)
- [Step D Present Spec](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_D_PRESENT_SPEC_2026_06_06.md)
- [Step D D1 Review Packet Fixtures](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_D_D1_REVIEW_PACKET_FIXTURES_2026_06_06.md)

Board anchors:
- `#102`: LSWR Phase 0; F3/F4/P42 accepted and merged through post `#2878`.
- `#94`: verified-outcome stream and output-to-memory ingestion substrate.
- `#92`: output / expression lane and `present()` honesty surfaces.
- `#6`: memory graph substrate and `present_outcome` cohort policy.

## Implementation Status - 2026-06-15

E0-E3 are implemented on Agent-Bridge `master` at `7523241`.

Implemented surfaces:

- E1 pure classifier: `classify_outcome_admission`.
- E2 read-only projection: `lswr_outcome_admissions`.
- E3 dry-run adapter: `lswr_outcome_admissions_dry_run`.

The E3 adapter is dry-run only:

- transforms only `training_eligible` admissions into #94-compatible
  `present_outcome` candidate rows;
- reuses the existing #94 `build_outcome_memory` constructor;
- exposes no `dry_run=false`, `max_writes`, `write`, `persist`, or
  `memory_save` input;
- calls no store write API and does not invoke `present_outcomes_ingest`.

Runtime profile boundary:

- `AGENT_BRIDGE_TOOL_PROFILE=all`: E3 is visible.
- `AGENT_BRIDGE_TOOL_PROFILE=standard`: E3 is not visible.
- `AGENT_BRIDGE_TOOLSET=codex-essential`: E3 is not visible.

Verification evidence from 2026-06-15:

- `cargo test -p ab-bridge lswr_outcome_admission -- --nocapture`
  passed with 17 focused tests.
- `cargo test -p ab-bridge present_is_niche_opt_in_and_registers_under_all -- --nocapture`
  passed.
- `cargo test -p ab-bridge lswr_outcome_admissions_dry_run_schema_has_no_write_switch -- --nocapture`
  passed.
- `cargo check -p ab-bridge --all-targets` passed with only existing warnings.
- A deployed all-profile MCP stdio `tools/list` probe returned
  `has_e3=true`, input properties exactly `limit`, `max_candidates`,
  `window_secs`, and `additionalProperties=false`.
- Standard and Codex-essential stdio probes returned `has_e3=false`.
- A non-empty runtime probe using a temporary Step D artifact and outcome
  sidecar returned `candidate_count=1`, `dry_run=true`, `writes_state=false`,
  `memory_kind=present_outcome`, and a deterministic
  `outcome_<artifact_id>` candidate key.
- The non-empty dry-run probe is now repeatable with:
  `scripts/lswr_e3_dry_run_smoke.sh`. It creates only temporary Step D files and
  #94-compatible E3 candidate previews; it performs no MCP call and no memory
  write.

E4 remains intentionally unopened. A manual opt-in write path requires a
separate owner approval and a fresh dry-run-first design slice.

The E4 approval-before-code design package is
[Step E4 Manual Opt-In Write Design](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4_MANUAL_OPT_IN_WRITE_DESIGN_2026_06_15.md).

## 0. Purpose

Step D proved that LSWR world results can be expressed as present-compatible
review artifacts without laundering lower-layer failures.

Step E decides which, if any, of those artifacts can later feed the existing
`#94` verified-outcome / memory-ingestion stream.

This is a learning boundary, not another presentation layer.

Step E answers:

> When an LSWR world result has been rendered into a human-review artifact, what
> exact evidence lets us persist it as a verified outcome, and what evidence must
> keep it audit-only?

## 1. Current Verified State

Relevant LSWR state:

- F3 `no-green-but-inert` is closed: model changes with frozen render stay
  `not_verified`.
- F4 `expected_effect` is closed: an applied patch whose declared visual effect
  fails stays `not_verified`.
- P42 is closed: Step D / `world_present` review artifacts preserve
  `expected_effect_clause_failed` as `not_verified` through present-compatible
  HTML and dual-encoded payload.
- Agent-Bridge `master` contains P42 at `62025a1`.

Relevant `#94` state:

- `present_outcomes` exists as a read-only verified-outcome sidecar projection.
- `outcomes_memory_drift` exists as a read-only output-to-memory gap report.
- `present_outcomes_ingest` exists as an opt-in, capped, `dry_run=true` default
  write path into ordinary memory rows of kind `present_outcome`.
- `present_outcome` rows are excluded from graph-coverage denominators and do
  not fabricate graph edges.
- `present_outcomes_ingest` writes only after the existing output-lane
  falsifier gate admits a record.

Important mismatch:

`present()` verification proves the expression artifact rendered honestly. It
does not, by itself, prove the LSWR world claim is true.

Therefore an LSWR Step D HTML artifact can be a valid `present()` outcome while
the embedded world packet is still `not_verified`. Step E must gate on both
layers.

## 2. Non-goals

Step E does not:

- change `present_outcomes` gate semantics in this slice;
- call `present_outcomes_ingest(dry_run=false)` automatically;
- add memory rows during design or validation;
- treat human approval as proof that the world claim became verified;
- make `world_*` tools visible in Codex essential profile;
- write graph edges or modify PageRank / coactivation behavior;
- ingest raw screenshots or OCR output as primary evidence;
- create a second ingestion substrate parallel to `#94`.

## 3. Two-Layer Evidence Model

LSWR ingestion needs two separate verdicts.

### Layer A: World Evidence

This comes from the LSWR world envelope / present packet:

```text
source_world {
  schema: "agent_bridge.lswr.present_packet.v0",
  world_tool: "world_patch" | "world_query" | "world_visibility_query",
  verdict: "verified" | "not_verified" | "blocked",
  reason: string|null,
  machine_payload: {
    verify: object,
    patch_result?: object|null,
    expected_effect?: object|null,
    action_result?: object|null
  },
  provenance: {
    verified_to: string|null,
    verify_method: string
  },
  ingestion: {
    allowed: false,
    reason: string
  }
}
```

World evidence decides whether the LSWR claim itself is true enough to learn.

### Layer B: Expression Evidence

This comes from the output lane:

```text
expression {
  present_artifact_id: string,
  verify_status: "rendered_ok" | "blank" | ...,
  embody_status?: "embodied" | "not_applicable" | ...,
  interactive_status?: "verified" | "not_applicable" | ...,
  decision?: "approved" | "rejected" | ...
}
```

Expression evidence decides whether the review artifact was faithfully shown to
the human/operator and can be audited through `#94`.

Both layers must pass for a training-eligible LSWR outcome.

## 4. Admission Classes

Step E classifies each LSWR review artifact into one of three classes.

| Class | Meaning | Memory / training behavior |
|---|---|---|
| `training_eligible` | World claim verified and expression artifact verified | May later enter #94 via explicit dry-run-first ingestion |
| `audit_only` | Useful evidence, but not a verified learning label | May be retained as artifact / forum evidence; must not be a verified outcome memory |
| `rejected` | Unsafe, malformed, or contradicted evidence | Do not ingest; preserve as failure evidence only if useful |

Default is `audit_only`.

## 5. Training-Eligible Gate

An LSWR outcome is `training_eligible` only if all conditions hold:

1. Source packet schema is `agent_bridge.lswr.present_packet.v0`.
2. Source packet `verdict == "verified"`.
3. Source packet `reason` is absent or null.
4. Source packet `provenance.verified_to` is non-null and non-empty.
5. Source packet has `machine_payload.verify.method`.
6. If `world_tool == "world_patch"`, `machine_payload.patch_result.applied == true`.
7. If `machine_payload.expected_effect` exists, `expected_effect.verified == true`.
8. If `machine_payload.action_result` exists, it is not `not_verified`.
9. Step D dual-encoded payload roundtrip matches the source packet.
10. Output-lane expression gate is eligible:
    - `verify_status == "rendered_ok"`;
    - `embody_status` absent, `embodied`, or `not_applicable`;
    - `interactive_status` absent, `verified`, or `not_applicable`;
    - if human decision is present, it is `approved`.
11. `ingestion.allowed` may remain false in the Step D packet, but the Step E
    classifier must record its own explicit admission decision. Step D's false
    value is a safety default, not a hidden permission bit.

If any condition fails, the result is not training-eligible.

## 6. Audit-Only Gate

The result is `audit_only` when it is useful evidence but not a verified label.

Examples:

- `verdict == "not_verified"`;
- `reason == "expected_effect_clause_failed"`;
- `reason == "render_frozen_after_patch"`;
- `reason == "pixel_coverage_zero"`;
- world verification passed, but expression artifact failed to render;
- human reviewed and rejected the presentation;
- human approved the presentation, but the embedded world packet remained
  `not_verified`.

Audit-only records may be used for debugging, forum decisions, and future
falsifier design. They must not enter the verified training signal view.

## 7. Rejected Gate

The result is `rejected` when the evidence should not be retained as an outcome
candidate.

Examples:

- malformed packet;
- missing machine payload;
- unsupported schema;
- non-loopback or unsafe endpoint rejection;
- token mismatch in a human decision surface;
- dual-encoded payload extraction failed or disagreed with the source packet.

Rejected records may still be logged as tool errors or board findings, but they
are not LSWR outcome candidates.

## 8. Proposed Step E Record

A future classifier should emit a read-only admission record before any write
path exists.

```json
{
  "schema": "agent_bridge.lswr.outcome_admission.v0",
  "source": {
    "present_artifact_id": "ab_...",
    "world_tool": "world_patch",
    "world_verdict": "not_verified",
    "world_reason": "expected_effect_clause_failed",
    "verified_to": null,
    "verify_method": "live_viewport_pixel_coverage"
  },
  "expression": {
    "verify_status": "rendered_ok",
    "embody_status": "not_applicable",
    "decision": "approved"
  },
  "admission": {
    "class": "audit_only",
    "eligible": false,
    "reason": "source_world_not_verified"
  },
  "memory": {
    "write_allowed": false,
    "dry_run_required": true,
    "target_kind": "present_outcome"
  }
}
```

This record is a classifier output. It is not itself a memory write.

## 9. Relationship To Existing `#94` Surfaces

Step E should reuse `#94`, not fork it.

Recommended integration:

1. `world_present` / Step D produces a review packet with
   `ingestion.allowed=false`.
2. `present()` or file review rendering creates an output-lane artifact and may
   create ordinary `present_outcomes` sidecars.
3. Step E classifier reads the dual-encoded LSWR packet plus the output-lane
   expression outcome.
4. Step E emits `lswr.outcome_admission.v0`.
5. Only `training_eligible` admissions may be transformed into a #94-compatible
   verified outcome candidate.
6. `present_outcomes_ingest(dry_run=true)` remains the first write-path check.
7. `dry_run=false` remains explicit, manual, capped, and never automatic.

Do not feed raw Step D present sidecars directly into `present_outcomes_ingest`
as LSWR training proof. A rendered HTML artifact can carry a `not_verified`
world packet.

## 10. Canonical Admission Matrix

| World verdict | Expected effect | Expression | Human decision | Admission |
|---|---|---|---|---|
| `verified` | absent or verified | `rendered_ok` | absent | `training_eligible` |
| `verified` | verified | `rendered_ok` | approved | `training_eligible` |
| `verified` | verified | `rendered_ok` | rejected | `audit_only` |
| `verified` | verified | blank/broken | any | `audit_only` |
| `not_verified` | failed | `rendered_ok` | absent | `audit_only` |
| `not_verified` | failed | `rendered_ok` | approved | `audit_only` |
| `blocked` | any | `rendered_ok` | any | `audit_only` or `rejected` by reason |
| malformed | any | any | any | `rejected` |

The row "`not_verified` + approved" is load-bearing: human approval can approve
the presentation or next action, but it cannot convert the world claim into a
verified training label.

## 11. Acceptance Gates For Step E Implementation

### E1. Classifier purity

The first implementation should be a pure classifier over packet + expression
record fixtures. It writes nothing and calls no MCP tools.

### E2. No laundering

Fixtures with `expected_effect_clause_failed`, `render_frozen_after_patch`, and
`pixel_coverage_zero` must classify as `audit_only`, even if the HTML artifact
rendered correctly and a human approved it.

### E3. Positive eligibility

A verified world patch with `patch_result.applied=true`,
`expected_effect.verified=true`, non-null `verified_to`, and rendered Step D
artifact should classify as `training_eligible`.

### E4. Dual-encoding integrity

If the artifact payload cannot be extracted, or if the extracted payload differs
from the source packet, classify as `rejected`.

### E5. #94 compatibility without direct write

The classifier may report the `present_outcome` key / scope / tags a later write
would use, but the first implementation must not call `memory_save` or
`present_outcomes_ingest(dry_run=false)`.

### E6. Dry-run-first write path

When a write path is later opened, its first live validation must use
`dry_run=true` and show planned writes before any durable row is created.

## 12. Suggested Slices

### E0 - Policy Sign-Off

Accept this document as the controlling Step E policy.

### E1 - Pure Admission Classifier

Add a Rust pure function and fixture tests for the admission matrix.

No MCP tool is required yet.

### E2 - Read-Only Projection

Expose a read-only report over saved Step D artifacts:

```text
lswr_outcome_admissions(window, limit)
```

It should summarize `training_eligible`, `audit_only`, and `rejected` counts,
with reasons.

### E3 - Dry-Run Ingestion Adapter

Only after E1/E2 pass, add a dry-run adapter that transforms
`training_eligible` admissions into #94-compatible candidate rows.

### E4 - Manual Opt-In Write

Only after owner approval, allow a capped, explicit `dry_run=false` write path.

## 13. Recommended Next Decision

Recommended next action:

- Accept this policy as E0.
- Implement E1 pure classifier with fixture tests.
- Keep all memory writes disabled.

This keeps the learning boundary honest:

```text
World verified -> expression verified -> optional human acceptance
  -> Step E admission -> dry-run #94 candidate -> manual memory write
```

Any failed world verification remains useful evidence, but it is not a verified
training label.
