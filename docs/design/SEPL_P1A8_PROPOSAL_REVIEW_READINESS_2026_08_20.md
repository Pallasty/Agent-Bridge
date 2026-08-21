# SEPL P1A8 Proposal Review Readiness Projection

## Scope

P1A8 projects the structural topology of one integrity-verified P1A7 review
snapshot. The only new surface is the inherent
`SqliteStore::project_agent_md_proposal_review_readiness` method. There is no
new schema table, `StateStore`, MCP, CLI, scheduler, producer, policy, apply, or
runtime entry.

## Projection Contract

The projection reuses the complete P1A7 read and classifies its observation set
as exactly one of:

- `no_observations`;
- `single_disposition_observed`;
- `conflicting_dispositions_observed`.

The classification describes record topology only. It does not interpret any
disposition as correct, deduplicate reviewer labels, or infer that a review was
performed by a human. A domain-separated projection hash binds the proposal
record hash, source snapshot hash, all disposition counts, and classification.

## Trust Boundary

P1A8 always reports false for reviewer and human authentication, semantic
authority, quorum, winner selection, proposal approval, apply eligibility,
automatic apply, resource mutation, and lineage mutation. A single observed
disposition is not consensus; repeated labels are not distinct identities; an
`accept_candidate` observation is not approval.

## Non-Claims

P1A8 does not authenticate writers or reviewers, establish policy thresholds,
resolve conflicts, select a disposition, approve a proposal, reserve a lease,
invoke P1A1 CAS, mutate `AGENT.md`, append lineage, or enable execution.

## Test Floor

- empty, single-disposition, and conflicting snapshots classify deterministically;
- the projection hash changes when source snapshot order or counts change;
- P1A7 tampering and overflow continue to fail closed;
- all authority and mutation flags remain false;
- persisted rows, `AGENT.md`, and lineage remain unchanged.
