# Engram AB Specificity Scout Result

Date: 2026-07-27

Status: **CONDITIONAL SPECIFICITY CANDIDATE VALIDATED; INTEGRATION AND
DEPLOYMENT PENDING**

## Direct Agent-Bridge objective

The target is an observed Agent-Bridge retrieval failure, not an external model
integration:

- query: remote instruction injection into a running long-lived agent session;
- expected memory:
  `agentbridge_remote_session_steer_gap_20260529`;
- failure mode: the semantically strongest answer was displaced by broadly
  co-surfaced, lower-cosine memories.

All embeddings in this study came from the already configured local
Agent-Bridge embedding path. No third-party reviewer or model API was required.

## Frozen input

- source and installed binary commit:
  `e122fe1bbc8060a1033a64e5c86f2c86367fed16`;
- installed binary:
  `agent-bridge 0.14.0 (v0.14.0-1064-ge122fe1b)`;
- installed binary SHA-256:
  `364c2865490ab9e3bfc9d2bcca469757bede3806a5224ffbd01cb9cdbe06d9f3`;
- SQLite snapshot SHA-256:
  `25e8f8abf7aeac901020cbc50d27329b831929f60b5d4f6177c9b2537127493f`;
- active memories: 4,089;
- memory edges: 7,679;
- embedding backend: `gte-multilingual-base`, 768 dimensions.

The source snapshot remained unchanged across the read-only audits. MCP
runtime probes used separate disposable copy-on-write database clones and
`AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval`.

## Graph signal gate

The graph-reorganization hypothesis failed its admission gate:

| Metric | Observed |
|---|---:|
| trusted `cofires` / `co_referenced` degree | 0 |
| coactivation degree | 19 |
| maximum coactivation count | 1 |
| consolidated coactivation degree | 0 |
| `evolved` degree | 31 |
| same-project `evolved` degree | 3 |
| same-project `evolved` purity | 0.0968 |

Result:
`NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL`.

The `evolved` neighborhood is predominantly cross-project noise. It must not be
used as a clustered-reorganization retrieval signal.

## Root cause

Raw semantic retrieval already had the expected memory at rank 2 on the frozen
snapshot. In an installed-binary MCP replay with the current scoped semantic
pipeline, the expected memory had the highest cosine (`0.6875`) but reached only
rank 10 after the read-side coactivation multiplier:

```text
score *= 1 + 0.2 * ln(1 + page_coactivation_count)
```

With only `AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=1` changed, against an
independent clone of the same snapshot, the same installed binary returned the
expected memory at rank 1. Candidate generation, embeddings, scope aliases,
semantic weights, database content, and the coactivation writer were otherwise
unchanged.

## Matched read-only A/B

`recall_eval` now reproduces the production multiplier without graph writes.
The current 18-case corpus had active expected keys on the frozen snapshot.

| Arm | N | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| raw semantic, coactivation OFF | 18 | 0.667 | 1.000 | 1.000 | 0.824 |
| raw semantic, coactivation ON | 18 | 0.667 | 1.000 | 1.000 | 0.796 |
| scoped local+global, coactivation OFF | 15 | 0.533 | 0.800 | 0.800 | 0.639 |
| scoped local+global, coactivation ON | 15 | 0.133 | 0.333 | 0.667 | 0.247 |

For the observed case:

- scoped semantic, coactivation OFF: rank 1;
- scoped semantic, coactivation ON: rank 10.

The six related remote-session controls retained the expected target or
steering-chain family, while all six unrelated controls produced zero accepted
intent-gated rows. That intent-gated arm contains a case-family classifier and
is therefore supporting diagnosis only; it is not the basis for the general
rollout decision. The rollout decision rests on the generic coactivation OFF
A/B above.

## Rejected evidence

The older `scripts/eval/fixtures/retrieval_pairs.json` benchmark was run but not
used for the decision: only one of its nine expected-key families was active in
this snapshot; the other expected keys were absent. Its identical ON/OFF result
therefore measures fixture/store drift rather than ranking quality.

## Decision

The first candidate was the existing reversible configuration:

```text
AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=1
```

It passed the matched exact/related aggregate but failed live unrelated
acceptance. With the flag enabled, the generic negative control:

```text
怎么通过 ssh 远程登录服务器
```

returned the target remote-session steering memory at rank 3. The pre-existing
coactivation-ON arm also surfaced remote-session family rows on two unrelated
controls, although lower in the page. A global ON or OFF choice therefore does
not satisfy the specificity endpoint.

The machine-environment entry was removed immediately. Verification after
re-sourcing the environment returned
`AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=<unset>`. No already-running MCP
process had been restarted onto the rejected setting.

The successor candidate is conditional and default-off:

- strict remote + agent + session + steering intent: bypass coactivation for
  this query family;
- otherwise: suppress remote-session-steering family rows from semantic output;
- keep candidate generation, embeddings, semantic weights, coactivation
  recording, schema, and other retrieval families unchanged.

It is exposed only as:

```text
AGENT_BRIDGE_REMOTE_SESSION_SPECIFICITY_V0=1
```

The policy is inert unless all of these are true:

- mode is `semantic`;
- the caller supplies an explicit scope;
- that scope is the canonical Agent-Bridge project ID or is connected to it by
  the approved `AGENT_BRIDGE_PROJECT_SCOPE_ALIASES` registry.

FTS, hybrid, unscoped semantic searches, other projects, schema, stored
embeddings, and graph writes retain the prior path.

## Candidate acceptance

Every runtime observation below used a fresh copy-on-write clone of the frozen
snapshot and the newly built source binary.

### Exact, related, and unrelated controls

- main exact query: target rank 1;
- six related controls: steering family present in top 10 for 6/6;
- six unrelated controls: no steering-family row in top 10 for 6/6.

The target ranked 1 for three related controls, 2 for two controls, and 8 for
the decision-gap wording. The gate requires an accepted steering-family answer
within top 10, not that every paraphrase force the same row to rank 1.

### Generic and scoped regression

The unscoped 18-case semantic corpus is unchanged:

| Arm | N | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| candidate disabled | 18 | 0.667 | 1.000 | 1.000 | 0.796 |
| candidate enabled, no scope | 18 | 0.667 | 1.000 | 1.000 | 0.796 |

The ordered rank vector was identical. This is expected because an unscoped
call cannot activate the policy.

The 15 Agent-Bridge-local scoped cases improved without another expected-key
rank changing:

| Arm | N | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| current coactivation path | 15 | 0.133 | 0.333 | 0.667 | 0.236 |
| conditional candidate | 15 | 0.200 | 0.400 | 0.667 | 0.296 |

Case #8 moved from rank 10 to rank 1. The other 14 expected-key ranks were
identical between arms.

### Default-off parity

The installed pre-change binary and the new source binary were run concurrently
against independent snapshot clones with the feature unset. Pairing each query
inside the same Unix scoring second removes the existing time-decay field as a
confounder. All 18 compact semantic response texts were byte-identical on the
first attempt.

### Local checks

- specificity policy unit tests: 4 passed;
- `recall_eval` unit tests: 42 passed;
- aggregate graph-audit tests: 4 passed;
- `cargo build -p ab-bridge --locked --offline`: passed.

## Decision and remaining boundary

The conditional candidate passes its five frozen gates:

1. the main exact query returns the target at rank 1;
2. all six related controls retain the target or steering-chain family within
   top 10;
3. all six unrelated controls contain no remote-session-steering family row;
4. the 18-case generic semantic aggregate is non-inferior;
5. default-off output remains byte-identical.

It is eligible for source integration and a reversible default-off deployment.
This report does not itself claim integration, installed-binary replacement,
fresh-process activation, desktop MCP reconnect, or live-consumer acceptance.
