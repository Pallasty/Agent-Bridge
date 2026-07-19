# Engram G1.4 Candidate Protocol Preregistration Result

Date: 2026-07-18

Verdict: **PASS — DESIGN ONLY / FAIL CLOSED / NO DATA OR EXECUTION AUTHORITY**

## Delivered

- Public design contract:
  `scripts/eval/fixtures/engram_g14_candidate_protocol_preregistration_contract_v0.json`
  (`dca8ac03fbc915d70c6470492136ca9e554722aeed8d789e85714ece7e60ea41`).
- Independent semantic validator:
  `scripts/eval/engram_g14_candidate_protocol_preregistration.py`
  (`9e03d53b19eb9dd273ac6dc49cde7a9a93221de50be58eede37d25729374cd1c`).
- Adversarial checker:
  `scripts/check-engram-g14-candidate-protocol-preregistration.sh`
  (`49d3734eb52a73235cc858e7ae43d0de99999eb0f693f76661375e22683c5a92`).
- Design rationale and eval-index entry.

The contract binds the exact G1.3, authenticated-adapter preregistration, and
synthetic isolated-lab predecessor artifacts. It fixes the experiment arms,
30-group partition contract, two-phase candidate lock, bounded development
feedback, blinding, future sandbox profile, determinism rules, one-shot sealed
lifecycle, decision guards, redaction, and transition-specific human-audit
policy.

## Test-first evidence

The first checker run was intentionally red before the validator existed. It
failed with `FileNotFoundError` for
`scripts/eval/engram_g14_candidate_protocol_preregistration.py`. No production
or persistent state had been touched, so rollback was simply leaving the
isolated worktree unchanged while implementing the missing pure gate.

After implementation:

- the G1.4 checker rejected 660 recursive field, value, list-order, list-length,
  and JSON-type mutations through a semantic policy declared independently of
  the fixture;
- raw-byte whitespace drift failed the separate SHA-256 entrance pin;
- duplicate JSON fields and contract symlinks failed closed;
- the public hardlink case remained accepted while every execution/data
  authority stayed false;
- all ten public predecessor artifacts matched their pinned hashes;
- forbidden crypto, network, process, database, and dynamic-escape imports were
  absent from the validator and shared public reader; and
- no G1.4 symbol appeared under `crates/`.

## Predecessor-chain verification

The following gates passed from the same isolated worktree:

1. G0 real-failure intake checker;
2. G1 grouped-corpus design checker;
3. G1.1 freeze-preflight checker;
4. G1.2 role-review checker;
5. G1.3 corpus-freeze review checker;
6. authenticated freeze-authority adapter preregistration checker;
7. synthetic isolated-lab adapter checker (`259` checks,
   `PASS_SYNTHETIC_ISOLATED_LAB_NO_AUTHORITY`); and
8. this G1.4 preregistration checker.

Formatting and static checks also passed: Black, Python bytecode compilation,
Pyflakes, `json.tool`, `bash -n`, and `git diff --check`. `shellcheck` was not
installed, so no ShellCheck claim is made.

## Independent review and correction

The first read-only Codex review found three issues:

1. the semantic mutation seam still compared against the same fixture;
2. three validator implementation/execution receipt fields were not explicitly
   asserted false; and
3. prose said “one positive design fact” although several positive values
   describe frozen future requirements.

The validator was changed to declare every closed section, field, ordered list,
type, and value independently in code. The checker now explicitly and
generically rejects positive validator capability fields. The prose now says
“one positive boundary bit.” A fresh read-only review then returned `PASS`,
found no unenforced fixture field or expected-value mismatch, and reran the 660-
mutation checker successfully.

## Nono decision

The design adopts grok-build's useful nono shape—irreversible policy before
untrusted work, capability-oriented profiles, exact dependency/rule-order
review, platform-specific deny tests, and active-state telemetry—but rejects
graceful unsandboxed fallback and “active flag equals proven enforcement.”

The future public-synthetic harness must prove allowed and denied canaries for
filesystem, network, subprocess, plugin, inherited descriptor, environment,
clock/entropy, output, resource, and state-isolation behavior on each supported
OS. `nono` is one mechanism inside that profile, not the whole security proof.

## Authority boundary and next gate

No real key, private corpus, candidate code, manifest, freeze capability, run
plan, sealed result, runtime registration, store write, retrieval mutation,
unblinding, deployment, or promotion was created or observed.

Routine public validation and unchanged public-synthetic checks require no
human approval. Reversible failures roll back automatically; failed or
incomplete rollback must leave durable evidence and a durable lesson. Manual
safety audit remains reserved for real/private enablement, post-lock or post-
observation policy changes, unblinding/rerun, sandbox-policy widening, first
real runner enablement, or suspected exposure.

The only permitted next action is a separate default-off **public synthetic
G1.4 protocol-harness implementation gate**. It may implement and test the
closed protocol/sandbox interfaces with synthetic fixtures, but it still may
not implement the real candidate, access private partitions, consume real
freeze authority, execute the sealed experiment, or alter Agent-Bridge runtime
behavior.
