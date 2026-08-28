# R7 M2 shadow natural failure sample 01

Date: 2026-08-27 (America/Los_Angeles)

Status: retained natural real-task evidence in the anchored macOS production
ledger. M2 remains unadmitted.

## Why this is natural evidence

During the owner-authorized exact replay of the surviving legacy mechanics
report, the operator invoked `agent-bridge.real` directly. That bypassed the
installed wrapper's `AGENT_BRIDGE_STATE_DIR` injection, so the command could
not resolve the production private state root and failed closed with
`resident_m2_shadow_invalid_configuration`. The invocation was part of the
real deployment-recovery workflow; it was not an injected fixture or a failure
created to exercise the shadow evaluator.

The failed direct invocation changed no Resident file. Repeating the same
operation through the installed wrapper returned `already_recorded`, created
the expected legacy anchor, and preserved the report bytes. This supplied
verified evidence for a fresh warning-severity failure candidate while the
interactive owner session was active.

## Privacy-minimal candidate

The canonical signal preimage was the compact sorted JSON below:

```json
{"execution_surface":"direct_real_without_wrapper_state_injection","failure_code":"resident_m2_shadow_invalid_configuration","operation":"resident_shadow_exact_replay","schema":"agent_bridge.resident_m2_shadow_candidate_signal.v0","trigger_kind":"failure"}
```

Its SHA-256 is
`2653660c7ed669a120f18a78d8896f59d23a0b34cef2db74913f99b289ec9046`.

The canonical evidence preimage was:

```json
{"direct_real_result":"resident_m2_shadow_invalid_configuration","direct_real_state_mutation":"none","installed_commit":"db7203f2c048a24df4b4c54cc8c081154f38cf91","report_id":"shadow-8f03704a03546fa9f76f7f969aa7a3ba","report_sha256":"9ffc1c95ffba582762200e8835d7e50e6a484acfd0022199cfb2479fb2090a4e","schema":"agent_bridge.resident_m2_shadow_candidate_evidence.v0","wrapper_result":"already_recorded"}
```

Its SHA-256 is
`e384b5e70d17c4fa02b4b34c3f034a11cc41a04395412c035f271db92e0f81f9`.
The report persisted only those hashes and typed metadata:

- report ID: `shadow-fd9d8607029e3cbe4303818e08594693`;
- trigger: `failure`;
- severity: `warning`;
- evidence: `verified`;
- foreground: `active`;
- observed/evaluated: `1787882321000` / `1787882329000` Unix ms;
- UTC offset: `-420` minutes.

## Decision and continuity evidence

Preview and record both returned `would_wake=false` with sole suppression
reason `foreground_session_active`. Projected and actual provider calls were
zero, actual wakes were zero, and `m2_admitted=false`. Exact replay returned
`already_recorded`.

The private artifacts are:

- ledger ID: `shadow-ledger-91f60308073f41da9400f4d46f7afbb8`;
- 0600 report, 1,694 bytes, SHA-256
  `d76fe56cfab1c3adc9efbccb4b171e3d128ef8a4c6751e6ad2335efb4175eb85`;
- 0600 anchor, 260 bytes, SHA-256
  `9093c0b96c245fb63498864f8d3f8739d96b44a7f9382849f9eaa7e1c92e0277`;
- 0600 ledger receipt, 123 bytes, SHA-256
  `1231a5b40acec54fb77566ce4a9eefa8ec7602cc0b443396f64f187f5beca9a0`.

The anchor binds the same ledger ID, report ID, and exact report digest.

## Complete-ledger review

The installed review classified the new report as natural and the surviving
legacy report as mechanics. It returned two total reports, one natural failure,
one mechanics recovery, one natural suppression, zero provider calls, zero
wakes, and no active owner stop label. The natural suppression criterion is
now satisfied. Collection remains blocked by:

- fewer than three natural reports;
- fewer than two natural trigger kinds; and
- no natural `would_wake=true` report.

Continue only bounded manual collection during ordinary work. Do not add
candidate discovery, a scheduler, a provider call, or M2 admission.
