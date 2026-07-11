# Retrieval Traffic Class v42 Result

Date: 2026-07-10

Status: `DEPLOYED / COLLECTION_ONLY / APPLY_OFF / SHADOW_WAIT`

Protocol:
`docs/reports/goal-c-u/2026-07-10-retrieval-traffic-class-v42-prereg.md`

## Decision

Schema v42 and producer-boundary retrieval provenance are implemented,
verified on a private copy of the live v41 database, merged to remote master,
and deployed on the ThinkBook host.

This result authorizes labelled telemetry collection only. It does not
authorize outcome apply, importance changes, consumer filtering, ambient stage
2, a release, version change, tag, or remote CI.

## Source Identity

```text
remote master: 1f75ede032b36db321c3e767d620eac5a6a44c6e
binary:        agent-bridge 0.14.0 (v0.14.0-122-g1f75ede0; 1f75ede032b3)
binary sha256: 5ea3008c49bcc501e58f5cd6091b779350cb39b1b0105b3bce81b9439900ff7a
```

All commits introduced by this lane contain `[skip ci]`. No remote CI was
requested or used.

The lane absorbed remote temporal-truth projection commit `0b41db25` before
its final test/build pass. A separate local parallel commit, `733f584e`, was
not included in remote master: it exposed a model-facing telemetry-class
argument, overloaded retrieval mode with `eval:` prefixes, and changed
consumer/apply SQL, conflicting with the frozen additive v42 protocol. Its
branch remains available; no branch or commit was deleted. The installed
`733f584e` binary was replaced by the v42 binary during deployment.

## Implemented Boundary

- `retrieval_surfacing.traffic_class` is constrained to `unknown`, `organic`,
  or `eval`, defaults to `unknown`, and has a
  `(traffic_class, surfaced_at DESC)` index.
- Existing rows and compatibility-writer calls persist as `unknown`; no query,
  key, mode, timestamp, or process-name inference occurs.
- `memory_search` and semantic `session_bootstrap` capture
  `AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS` before their asynchronous write.
- Missing, empty, whitespace, and invalid values normalize to `unknown`;
  accepted values normalize case-insensitively.
- No MCP argument or tool schema exposes the traffic class.
- Repository benchmark and verifier subprocesses explicitly set `eval`.
- Production machine configuration explicitly defaults normal processes to
  `organic`.
- Existing outcome aggregate, consume, and apply SQL is unchanged. Outcome
  apply remains disabled.

## Verification

Local merged-tree gates:

```text
cargo fmt --all -- --check                         PASS
ab-store                                            429 passed
ab-bridge lib                                       1517 passed, 4 ignored
ab-bridge main                                      92 passed
ab-bridge integration/doc suites                    PASS
memory evidence + ambient offline fixtures          PASS
Python/shell syntax and git diff checks              PASS
```

Offline fixtures pin these ambient verdicts:

```text
missing class column       BLOCKED_NEEDS_TRAFFIC_CLASS
labelled but immature      WAIT
post-label unknown row     BLOCKED_PARTIAL_TRAFFIC_CLASS
organic thresholds met    OPEN
```

The fixture includes `traffic_class=eval, mode=bootstrap`; it is reported but
does not contribute to any ambient threshold.

## Copied-DB Gate

`scripts/verify-retrieval-traffic-class-v42.py` used SQLite online backup into
a verified-0700 temporary directory. Its aggregate-only output contains no
query text, memory key, MCP payload, source path, or temporary path.

Exact-candidate result:

```text
source schema                                      41
source retrieval_surfacing rows                    13682
source old-field sha256
  ab65d54a843f0ef9f38880497c014ec21e85bf0cd42dd5e0351ce6ddc3d15931
candidate schema                                   42
row count / old-field digest preserved             yes / yes
historical traffic classes                         unknown=13682
organic/eval historical rows                       0 / 0
column NOT NULL + CHECK + index                     PASS
organic search writer                              organic
eval search writer                                 eval
unset search writer                                unknown
invalid search writer                              unknown
eval semantic-bootstrap writer                     eval + mode=bootstrap
pre-v42 binary reopen/write                        PASS + unknown
```

The compatibility binary observed during the final gate was the then-installed
`733f584e` build. It reopened schema 42 and inserted through its old explicit
column list; SQLite supplied `traffic_class=unknown`.

## Deployment

The candidate was built from the clean final commit, independently matched to
remote master, passed the deploy feature-superset gate, and replaced only
`~/.local/bin/agent-bridge.real`. The wrapper was not modified.

```text
previous binary backup:
  ~/.local/bin/agent-bridge.real.bak-deploy-usebin-20260710T193041

machine.env sha256 before:
  14a3dbc5b7e4c6dacb07ef886550b6a50aa6be59d9bbf78cdaed351892088649
machine.env sha256 after:
  42c57fbdb00192d1be7a2d0765be45d18277dba9895c9e29a2758a7aa529ab08
```

The machine-env change adds only a guarded organic default and updates the
existing HOLD comment. The effective daemon environment after restart is:

```text
AGENT_BRIDGE_OUTCOME_COLLECTOR=1
AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=organic
AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY=0
```

Daemon, daemon-http, and Palace services are active. Daemon-http and Palace
health endpoints both returned HTTP 200.

Live migration preserved all rows at the pre-migration boundary:

```text
schema                                             42
pre-migration max id                               13682
rows at id <= 13682                                13682
old-field sha256 at id <= 13682
  ab65d54a843f0ef9f38880497c014ec21e85bf0cd42dd5e0351ce6ddc3d15931
total rows immediately after migration             13682
traffic classes immediately after migration        unknown=13682
traffic/time index                                 traffic_class,surfaced_at
```

No live search/bootstrap call was manufactured to create organic acceptance
evidence. Existing MCP processes were deliberately left connected per owner
direction; old binaries can continue writing rows, but the schema default makes
those rows `unknown`, which blocks rather than launders causal admission.

## Post-Deploy Read-Only Audit

```text
causality verdict                                  BLOCKED_PARTIAL_TRAFFIC_CLASS
mature pending rows                                3975
existing decay / reinforce candidate memories      300 / 42
organic decay / reinforce candidate memories       0 / 0
ambient verdict                                    WAIT_LABELLED_DATA
ambient unknown bootstrap rows                     9199
ambient organic exposures / stamps                 0 / 0
no-write invariants                                PASS
outcome apply authorized                           false
ambient stage2 authorized                          false
```

Three historical `eval:fts` mode rows from the excluded parallel prototype are
visible only as historical `unknown`; v42 does not infer or backfill them.

## Rollback

Binary rollback is the recorded backup copy followed by bounded service
restart/reconnect. Machine-config rollback removes the guarded traffic-class
export; missing provenance then fails closed to `unknown`. Schema downgrade is
neither required nor recommended: the previous binary was proven able to open
schema 42, and its omitted insert column defaults safely to `unknown`.

Re-enabling `AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY` remains forbidden until a
separate, preregistered organic-only shadow passes and receives explicit
authority.
