# BioCortex Retrieval Agent Technical Attestation

Date: 2026-06-11

## Decision

Agent technical attestation: `approve_continue_design`.

This approves continued design work for BioCortex retrieval influence under
read-only shadow or explicit opt-in constraints only. It does not approve
default `memory_search` influence, runtime reranking, approval writes, or
default search-order changes.

Machine-readable packet:

- `docs/design/fixtures/biocortex-retrieval-agent-technical-attestation-2026-06-11.json`

## Scope

The attestation covers technical evidence and behavioral risk visible from the
current Agent-Bridge shadow surface:

- runtime adapter approval remains false;
- default search order remains unchanged;
- the review packet is read-only and writes no approval state;
- agent attestation cannot replace human authorization;
- human authorization scope remains `none`.

The attestation does not cover a production reranker, a default
`EmbeddingBackend`, a BioCortex default backend, background learning, or any
memory mutation path.

## Evidence Reviewed

- `scripts/verify-biocortex-retrieval-shadow.sh` passed with
  `AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs`.
- Current and hard holdout corpora pass `candidate-strong` offline gates.
- Acceptance corpus keeps `runtime_adapter_approved=false` and
  `default_search_order_changed=false`.
- Approval packet preview reports:
  - `approval_state=not_approved`;
  - `runtime_adapter_approved=false`;
  - `approval_writes_allowed=false`;
  - `default_search_order_change_allowed=false`;
  - `ready_for_human_approval_review=false`;
  - `agent_technical_attestation.can_authorize_runtime_influence=false`;
  - `human_authorization.status=not_authorized`;
  - `human_authorization.scope=none`.

## Residual Holds

This attestation intentionally leaves the approval packet not ready for human
approval review because several runtime-influence details are still missing:

- p95 side-signal latency for the target runtime surface;
- live MCP default-disabled proof packet;
- exact default-ordering call site for any future influence design;
- explicit absent, slow, and error behavior for the future runtime path.

These holds are compatible with `approve_continue_design`. They are not
compatible with approving default retrieval influence.

## Boundary

The agent may recommend continued technical work because it is the first user of
the memory system and can inspect retrieval behavior directly. The human owner
still decides trust-boundary scope. Therefore this attestation is advisory and
cannot become authorization by itself.
