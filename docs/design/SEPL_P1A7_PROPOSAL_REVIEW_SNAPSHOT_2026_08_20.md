# SEPL P1A7 Proposal Review Snapshot

## Scope

P1A7 reads one P1A5 proposal and its P1A6 review observations as a bounded,
deterministically ordered snapshot. The only new runtime surface is the
inherent `SqliteStore::read_agent_md_proposal_review_snapshot` method. There is
no `StateStore`, MCP, CLI, scheduler, producer, apply, or runtime-policy entry.

## Snapshot Contract

The method requires a lowercase SHA-256 proposal id, verifies the referenced
P1A5 artifact, and reads at most 257 P1A6 rows in one SQLite read transaction.
The 257th row is only an overflow sentinel: more than 256 observations fails
closed instead of returning a truncated or misleading set.

Rows are ordered by `(reviewed_at ASC, review_id ASC)`. Every row must bind the
requested proposal id and the transaction-observed P1A5 record hash, and its
P1A6 record hash is recomputed. The snapshot hash length-frames the domain,
proposal id, proposal record hash, observation count, and ordered review record
hashes. Empty snapshots are valid and content-addressed.

## Conflict Semantics

The snapshot reports counts for `accept_candidate`, `reject_candidate`, and
`defer`, plus the number of distinct dispositions. More than one observed
disposition sets `conflicting_dispositions_observed=true`.

This is observation, not adjudication. Conflicts are preserved rather than
resolved. Counts are counts of records, not authenticated reviewers or votes.
Repeated reviewer labels are not deduplicated and labels carry no identity
authority.

## Trust Boundary

P1A7 always reports:

- `external_writer_exclusion_verified=false`;
- `reviewer_identities_authenticated=false`;
- `human_reviews_authenticated=false`;
- `semantic_review_authority_granted=false`;
- `quorum_established=false`;
- `winner_selected=false`;
- `eligible_for_apply=false`;
- `automatic_apply_allowed=false`;
- `resource_content_mutated=false`;
- `lineage_mutated=false`.

The read transaction gives a consistent SQLite observation point. It does not
exclude external writers before or after that point, authenticate the database
writer, prove that a human performed a review, or provide anti-rollback and
non-equivocation guarantees outside the local database.

## Non-Claims

P1A7 does not authenticate reviewers or producers, establish quorum, interpret
majority, choose a winning disposition, mark a proposal approved, authorize a
CAS commit, mutate `AGENT.md`, append resource lineage, reserve a lease, or
enable automatic execution.

## Test Floor

- empty snapshots are valid, deterministic, and content-addressed;
- mixed dispositions remain ordered and explicitly conflicting;
- snapshot count/hash and per-disposition counts are deterministic;
- P1A6 row or referenced P1A5 tampering fails closed;
- observation sets above 256 fail closed without truncation;
- proposal bytes, `AGENT.md`, lineage, and persisted rows remain unchanged.
