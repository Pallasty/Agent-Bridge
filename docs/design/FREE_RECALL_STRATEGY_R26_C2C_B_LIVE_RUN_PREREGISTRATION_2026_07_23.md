# Free Recall Strategy R26 — C2C-B Bounded Live Run Preregistration

Date: 2026-07-23

Status: **R27 SOURCE IMPLEMENTED / R26 ATTEMPT-1 INCOMPLETE / NO RETRY**

Parent acceptance: R25 C2C-B startup wiring.

## 1. Goal

R26 proposes one bounded, disposable integration run that proves the existing
R25 normal-process assembly can observe one non-empty `session_curate` batch
through the real macOS Keychain reader and persist one finalized episode into
a disposable SQLite database.

It must prove the whole path, not merely a constructor:

```text
explicit MCP CLI authorization
  -> readiness read
  -> open -> item(s) -> close
  -> disposable SQLite finalized projection
  -> exact Keychain cleanup
```

## 2. Fixed run envelope

The later authorization must name exactly one fresh directory created with
`mktemp -d /tmp/ab-r26-c2c.XXXXXX` and exactly one database inside it:

```text
<fresh directory>/state.db
```

The directory must not be an existing Agent-Bridge state location, a project
worktree, or a user data directory. It is removed only after the post-run
SQLite receipt is captured.

The Keychain service remains fixed:

```text
com.agent-bridge.episode-ref.v1
```

The two only permitted disposable accounts are:

```text
active-epoch
key:c2c-live-<16 lowercase hex characters>
```

Both require metadata-only absence preflight. The key material is generated
in process, is exactly 32 random bytes, is never printed or passed through an
argument/environment/file, and is zeroized after the pointer write. The key
account is created first; `active-epoch` last. Cleanup deletes the pointer
first, then the key account, and verifies absence for both exact accounts.

## 3. Exact proposed R27 source surface

The formerly preregistered narrow R27 surface was implemented in
`1b97b1ca`. It remains default-off; its one attempted live run is recorded
below as incomplete:

| Path | Purpose |
| --- | --- |
| `crates/bridge/Cargo.toml` | Default-off R26 live-lab feature depending on accepted R25. |
| `crates/bridge/src/bin/episode_observation_c2c_live_lab.rs` | One isolated stdio-MCP fixture driver; no production startup change. |
| `crates/store/Cargo.toml` | Default-off companion lab feature. |
| `crates/store/src/lib.rs` | Feature- and macOS-gated lab declaration only. |
| `crates/store/src/episode_observation_c2c_keychain_macos_c2c_live_lab.rs` | Generate/write/clean the two exact disposable Keychain accounts without shell password arguments. |
| `scripts/eval/free_recall_strategy_r27_c2c_live_lab_source.py` | Static authority, cleanup, and no-secret checker. |

The production R25 runtime modules, C2B reader, Hub seam, SQLite schema,
MCP registry, retrieval, sync/export, deployment, and default feature set
remain unchanged.

### Attempt-1 receipt

One bounded attempt reached an empty SQLite episode receipt and is therefore
`INCOMPLETE`, not acceptance. The generated accounts were handled only by the
guard's exact cleanup/postcheck path; no account identifier or secret is
recorded here. Root cause was a source mismatch between the active epoch
pointer and the prefixed key-account name. The source correction is reviewable,
but this attempt is not retried under R26.

## 4. Fixture and acceptance requirements

The driver starts a separately built default-off binary only with:

```text
agent-bridge mcp --episode-observation keychain-macos-v1
```

and a fixture-specific database path. It initializes stdio MCP, writes a
small synthetic curation candidate set through existing public MCP calls, then
invokes exactly one `session_curate` request. The fixture must yield at least
one successful core memory save; empty candidates are an invalid fixture, not
a passing no-episode result.

`AGENT_BRIDGE_DB` may carry only the fixture database path to the child
process. It is not an observation enablement input and may not carry a
Keychain account, epoch, key, token, or arbitrary fixture payload.

Acceptance requires all of the following:

1. the normal process remains responsive after the run;
2. the disposable database contains exactly one finalized CurationBatch
   episode with contiguous item positions and matching close count;
3. no raw memory key, Keychain account, epoch, key bytes, or backend error
   appears in MCP stdout, stderr, logs, or the result document;
4. Keychain postchecks confirm both exact disposable accounts are absent;
5. the disposable database receipt is captured before deleting its directory;
6. core curation succeeds independently of observation failure paths.

## 5. Failure and rollback contract

Any readiness, open, item, close, fixture, process, or persistence failure is
`INCOMPLETE`, never a live acceptance. The guard cleans only entries it wrote.
If interruption prevents cleanup confirmation, the result records the one
public generated key-account identifier and stops; recovery may delete only
that identifier and `active-epoch` in the fixed service.

No pre-existing item may be accessed, updated, or deleted. The run must not
unlock Keychain, alter ACLs/search lists, use `-A`, enumerate the Keychain, or
deploy/release/merge any artifact.

## 6. Negative authority

The R27 source commit authorizes no execution by itself. It grants no Keychain
read/write/delete, normal-process launch, MCP fixture execution, database
creation, merge to master, release, deployment, or follow-on training work.

The next valid action is explicit owner authorization for the exact R27 source
surface and, separately, the one R26 live invocation defined above.
