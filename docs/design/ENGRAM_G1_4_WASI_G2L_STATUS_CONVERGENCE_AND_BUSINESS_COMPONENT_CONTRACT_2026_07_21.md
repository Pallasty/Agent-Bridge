# Engram G1.4 WASI G2L status convergence and business component contract

Date: 2026-07-21  
Status: `G2L_CLOSED_LIVE__NEXT_CONTRACT_DESIGN_ONLY`

## 1. Purpose

This document is the canonical status and handoff record for the G2L lane. It
separates the completed clock-probe proof from the next product-facing design
question: what contract a future business component must satisfy before any
production integration is considered.

G2L is not a production plugin system. It is a narrowly scoped, default-off,
explicitly invoked, hash-pinned WASI component execution proof.

## 2. G2L final status

The following claims are closed:

| Claim | Status | Evidence |
| --- | --- | --- |
| Canonical typed-report WIT contract | accepted | `ENGRAM_G1_4_WASI_G2L_COMPONENT_BUILD_RESULT_2026_07_21.md` |
| Component construction and host adapter | accepted | `ENGRAM_G1_4_WASI_G2L_EXECUTION_HOST_RUNTIME_RESULT_2026_07_21.md` |
| Release build and deployment | accepted | `ENGRAM_G1_4_WASI_G2L_RELEASE_DEPLOYMENT_RESULT_2026_07_21.md` |
| Direct deployed-binary execution | verified | same release result |
| Reconnected MCP process using deployed binary | verified | same release result; forum #166 post #4983 |
| Dynamic registry or arbitrary component exposure | not implemented | intentional boundary |

The live runtime is therefore sufficient for the G2L proof. No additional
G2L implementation, deployment, or MCP exposure is currently required.

## 3. Historical records and resolution

The following records remain valuable as audit history but no longer describe
the current state:

| Record | Resolution |
| --- | --- |
| `ENGRAM_G1_4_WASI_G2L_EXECUTION_AUTHORIZATION_DRAFT_2026_07_21.md` | superseded by the owner authorization and the final build/runtime/deployment receipts |
| `ENGRAM_G1_4_WASI_G2L_WIT_COMPONENT_LINKER_AUTHORIZATION_PREREGISTRATION_2026_07_21.md` | superseded by the accepted structural contract and execution receipts |
| `ENGRAM_G1_4_WASI_G2L_WIT_ABI_CONTRACT_RECONCILIATION_2026_07_21.md` | resolved by selecting the canonical `typed-report` contract |
| `ENGRAM_G1_4_WASI_G2K_REPRODUCIBILITY_EVIDENCE_PREREGISTRATION_2026_07_21.md` | remains an optional, separate evidence lane; it does not block G2L |

These historical packets must not be read as active authorization gates. They
also must not be deleted: retaining them preserves why the contract and
authority boundaries changed.

## 4. Next objective: business component contract

The next implementation should not start from a registry or from a production
component. It should first freeze a contract for one synthetic business
component that can be reviewed independently of runtime admission.

The contract design must define:

1. **Input envelope** — explicit version, invocation ID, tenant/session scope,
   bounded payload, and deterministic clock policy.
2. **Output envelope** — typed report, schema/version, bounded size, explicit
   success/failure, and an evidence reference; prose is never the authority.
3. **Capability imports** — an allow-list of the minimum WASI interfaces; no
   ambient filesystem, network, subprocess, entropy, or unrestricted clock.
4. **Determinism and replay** — fixed fixture, hash-pinned component, bounded
   resource budget, and a replay receipt that can distinguish identical output
   from merely successful execution.
5. **Failure semantics** — timeout, malformed output, capability violation,
   hash mismatch, and host unavailability must fail closed and must not become
   a green result.
6. **Admission boundary** — the design must state which fields are review-only
   and which, if any, could later be promoted; this phase grants no registry,
   production, MCP, candidate/private-data, or live-write authority.

The first candidate should remain a public synthetic component. A suitable
shape is a deterministic world-state transformation/report fixture, not a
real candidate model, private corpus, or user-data processor.

## 5. Non-goals for this phase

- no dynamic component/plugin registry;
- no arbitrary component upload or remote execution;
- no default-profile MCP tool exposure;
- no production state mutation or live-store writes;
- no native sandbox claim;
- no candidate/private corpus or real experiment;
- no dependency promotion merely because the contract is accepted.

## 6. Acceptance gates for the next lane

The next contract-design lane is complete only when an independent reviewer can
answer yes to all of the following:

- the WIT and envelope schemas are byte-pinned;
- every import and resource limit is explicit;
- the happy path and each fail-closed path have synthetic fixtures;
- replay evidence is independent of the component's own success claim;
- the contract cannot be interpreted as production or registry authorization;
- a later implementation lane can be opened without revising the boundary
  retroactively.

Only after this design gate should a separate owner decision consider a
default-off synthetic implementation. Native packaging, registry design, and
production integration remain separate decisions.

## 7. Recommended order

1. Keep G2L closed and deployed as-is.
2. Use this document as the canonical G2L status pointer.
3. Decide separately whether G2K reproducibility receipts are worth collecting.
4. Review and, if accepted, implement the public synthetic business-component
   contract.
5. Defer registry, production integration, and native sandbox work.
