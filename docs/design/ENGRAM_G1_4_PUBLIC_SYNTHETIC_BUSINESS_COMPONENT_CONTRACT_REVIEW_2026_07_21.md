# Engram G1.4 public-synthetic business component contract review

Date: 2026-07-21  
Verdict: `DESIGN_ACCEPTED__IMPLEMENTATION_GATE_CLOSED`

## 1. Scope

This is an independent read-only review of
`ENGRAM_G1_4_PUBLIC_SYNTHETIC_BUSINESS_COMPONENT_CONTRACT_2026_07_21.md` and
its WIT/JSON fixtures. It reviews contract consistency, hash pins, import
policy, admission flags, deterministic arithmetic, and replay prerequisites.
It does not build, bind, execute, register, deploy, or expose a component.

## 2. Finding and correction

The first contract revision had a material ambiguity: it required canonical
JSON in prose but did not freeze the serialization profile in the JSON
fixture. It also had no invocation-ID format. That would have allowed multiple
implementations to claim conformance while producing different hashes or
reusing an attempt identity.

The contract was corrected before acceptance:

- serialization is now `rfc8785-json-safe-integer-v0`;
- UTF-8, lexicographic keys, integer-only safe range, duplicate-key rejection,
  unknown-field rejection, and invalid-UTF-8 rejection are explicit;
- invocation IDs must match `^g14-biz-v0-[a-z0-9]{16}$`;
- replay must use a distinct ID and a failed ID cannot be reused;
- the contract JSON SHA-256 was recomputed and updated.

## 3. Independent checks

The read-only checker passed all 12 assertions:

- WIT and contract JSON byte pins match the design document;
- the WIT contains exactly one `evaluate` export;
- the WIT contains zero actual imports;
- the capability import list is empty;
- all admission flags are false;
- the invocation-ID pattern is present and exact;
- the canonical serialization profile is present;
- the fixture arithmetic independently derives `occupancy-per-mille=750`;
- the fixture report code is `WORLD_STATE_V0`; and
- `git diff --check` passes.

## 4. Acceptance boundary

The design contract is accepted as a stable input to a future implementation
review. This review does **not** open that implementation review. In
particular, it grants no authority for:

- WIT binding or component construction;
- Cargo dependency or linker selection;
- runtime registration or MCP exposure;
- release build, deployment, or canary;
- production writes;
- candidate/private data; or
- native sandbox or clock-isolation claims.

The next admissible action is a separately authorized public-synthetic
implementation gate whose checker must independently exercise the listed
happy path and fail-closed matrix.
