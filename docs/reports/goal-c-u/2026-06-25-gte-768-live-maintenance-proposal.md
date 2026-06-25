# GTE 768 Live Maintenance Proposal

Date: 2026-06-25

Status: `PROPOSAL_READY_FOR_OWNER_REVIEW / LIVE_CUTOVER_NO_GO`.

Scope: docs-only proposal for a future Agent-Bridge GTE 768 live maintenance
window. This proposal does not approve live DB mutation, live reindex,
deployment, runtime env changes, or production `memory_search` changes.

## Decision Stub

Recommended owner decision for this packet:

```json
{
  "owner_decision": "review_live_maintenance_proposal_only",
  "proposed_implementation_commit": "33d55e0e5e0ee61fd7d248f0be8aea55a1d2ddd7",
  "proposed_reader_compatibility_mode": "atomic_node_cutover_only",
  "live_gte_reindex_authorized": false,
  "live_db_mutation_authorized": false,
  "deploy_authorized": false,
  "runtime_env_switch_authorized": false,
  "default_memory_search_change_authorized": false,
  "rollback_confirmed": false
}
```

The owner may accept this as a planning proposal, but a separate final
authorization packet is still required before execution.

## Evidence Base

Source commits:

```text
c782979 docs(memory): record GTE canonical rehearsal
1f266a9 docs(memory): add GTE owner review packet
cbfaa7e test(memory): adjudicate GTE case14 recall target
33d55e0 test(memory): add GTE reader compatibility probe
```

Primary packets:

```text
docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-rehearsal.md
docs/reports/goal-c-u/2026-06-25-gte-768-case14-miss-review.md
docs/reports/goal-c-u/2026-06-25-gte-768-reader-compatibility-probe.md
docs/reports/goal-c-u/2026-06-25-gte-768-owner-review-packet.md
docs/reports/goal-c-u/2026-06-25-gte-768-mac-live-migration-verification.md
docs/reports/goal-c-u/2026-06-25-gte-768-mac-stale-reader-cleanup.md
```

Rollback companion draft:

```text
docs/reports/goal-c-u/2026-06-25-gte-768-rollback-packet-draft.md
```

## Current Node Facts

aio2 / ThinkBook, observed 2026-06-25 after Mac migration:

```text
repo_head=a9eaa6d
installed_binary=/home/pallasting/.local/bin/agent-bridge.real
installed_binary_sha256=cb76bf46963aa90dc496dad4ea7bd17e897be6525c9174e9449b40dacae147e7
installed_binary_bytes=67179000
doctor_ok=true
doctor_fails=0
doctor_warns=0
live_db=/home/pallasting/.local/share/agent-bridge/state.db
live_active_total=500
live_embedded=491
live_null_or_empty=9
live_dominant_backend=all-MiniLM-L6-v2
live_stale_vectors=253
live_stale_frac=0.515
live_gte_good=0
live_old_or_non_gte_active_embedded=491
live_readers_using_gte=0
live_readers_not_using_gte=4
```

Mac, observed over SSH 2026-06-25 after user-completed full migration:

```text
host=maxiaodeMac-Pro.local
ssh=pallasting@100.91.146.24
installed_binary=/Users/pallasting/.local/bin/agent-bridge.real
installed_binary_sha256=886da427f62726472f67972b31bad960fc0d16a093a287a3dd068f9439eabf69
doctor_ok=true
doctor_fails=0
doctor_warns=2
doctor_warning_summary=3 MCP server(s) all current .real; missing ab-system-control desktop helpers
live_db=/Users/pallasting/Library/Application Support/agent-bridge/state.db
live_active_total=3248
live_embedded=3248
live_null_or_empty=0
live_dominant_backend=gte-multilingual-base
live_dominant_bytes=3072
live_dominant_dim=768
live_gte_good=3248
live_gte_bad_dim=0
live_old_or_non_gte_active_embedded=0
```

Mac live-store note: the current Mac live DB is now verified as a full GTE 768
store by direct SQL invariants. The stale MCP reader blocker was cleared:
post-cleanup doctor reports all MCP servers are current `.real`. Mac
`continuity-report --json` still reports `embedded=0`, which contradicts direct
SQL and should be fixed or explicitly waived before final acceptance.

## Model Artifacts

The core GTE model files match on aio2 and Mac:

```text
model.onnx              5b9f03fdc40350a78fa064b4cfb6bf9a229a7c40aa87736f537e3ebd00aa2b86
tokenizer.json          3a56def25aa40facc030ea8b0b87f3688e4b3c39eb8b45d5702b3a1300fe2a20
config.json             6ef2538d4286a7cd18d05225f659d8a1bceca7adb01c186868e53dbd4f822e17
special_tokens_map.json 8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835
tokenizer_config.json   24cebbf2ef20fc317256e03e52ac7b2ca326586f946a8427ecac036332bf0933
```

aio2 also has `asset-manifest.txt`:

```text
asset-manifest.txt 217f19f0481f08a9a8f8ea09b7830b4366bda989f0359f32aedbdb9c128c8833
```

Mac did not have `asset-manifest.txt` during the read-only checks. This is not a
model-core hash mismatch, but the final packet should either install the
manifest on Mac or explicitly waive it.

## Proposed Compatibility Mode

Proposed mode:

```text
reader_compatibility_mode=atomic_node_cutover_only
```

Reason:

- copied-DB reader probe passed post-reindex invariants;
- mixed-reader support was not proven;
- live aio2 readers are still non-GTE;
- aio2 live DB is still 384-era;
- Mac has a verified GTE 768 live DB and stale MCP readers are cleared.

Reader compatibility probe summary:

```text
pre_db:  active_total=3022 dominant=multilingual-e5-small dim=384 rows=1628 stale_for_target=3022
post_db: active_total=3022 dominant=gte-multilingual-base dim=768 rows=3022 target_good=3022 stale_for_target=0
post_reindex_invariant=pass
mixed_reader_support=not_proven
recommended_mode=atomic_node_cutover_only
```

## Proposed Maintenance Sequence

This is the proposed sequence for a future approved window. It must not be run
until the owner signs a final authorization packet.

1. Announce a memory write freeze.
2. Confirm `origin/master` and both local checkouts are at the approved commit.
3. Confirm model artifact hashes on both nodes.
4. Run `doctor --json` on both nodes. Stop if fails are non-zero or if stale MCP
   rows reappear on the node being migrated.
5. Run `scripts/verify-gte-768-preflight.sh --live-cutover --strict` on aio2.
6. Run equivalent Mac preflight and confirm stale Mac MCP readers remain clear.
7. Stop all Agent-Bridge readers on the node being migrated.
8. Capture DB, WAL, SHM, and installed-binary backups.
9. Build or install the approved binary from `origin/master`.
10. Set `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base` and
    `AGENT_BRIDGE_ONNX_MODEL_DIR` only for the maintenance/reindex process
    until the final runtime env is chosen.
11. Run live reindex on one node only.
12. Verify backend and byte-length distribution before reconnecting readers.
13. Reconnect readers for that node.
14. Run `doctor --json`, capabilities, and `recall_eval`.
15. Repeat for the second node only after the first node is accepted.
16. End write freeze only after both node states and rollback paths are
    recorded.

## Command Templates

Read-only pre-window checks:

```bash
git fetch origin
git rev-parse origin/master
/home/pallasting/.local/bin/agent-bridge.real doctor --json
scripts/verify-gte-768-preflight.sh --live-cutover --strict
scripts/verify-gte-768-reader-compatibility-probe.sh \
  --pre-db /path/to/pre-reindex/copied/state.db \
  --post-db /path/to/post-reindex/copied/state.db \
  --strict
```

Live reindex command template, only after final owner authorization:

```bash
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
AGENT_BRIDGE_ONNX_MODEL_DIR="$HOME/.cache/agent-bridge/onnx-models" \
cargo run -p ab-store --example reindex_to_active_model -- "$LIVE_DB"
```

Post-reindex invariant check:

```bash
python3 - "$LIVE_DB" <<'PY'
import pathlib
import sqlite3
import sys

db = pathlib.Path(sys.argv[1]).resolve()
con = sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True)
con.execute("PRAGMA query_only=ON")
rows = con.execute("""
SELECT COALESCE(NULLIF(embedding_backend, ''), 'unknown') AS backend,
       LENGTH(embedding) AS bytes,
       COUNT(*) AS n
  FROM memories
 WHERE status='active'
   AND embedding IS NOT NULL
   AND LENGTH(embedding) > 0
 GROUP BY backend, bytes
 ORDER BY n DESC, bytes DESC, backend ASC
""").fetchall()
for backend, byte_len, n in rows:
    print(f"backend={backend} bytes={byte_len} dim={byte_len // 4 if byte_len else 0} rows={n}")
PY
```

Post-reconnect recall check:

```bash
AB_BASELINE_DB="$LIVE_DB" \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-bridge --example recall_eval
```

## Stop Conditions

Stop before live mutation if any are true:

- no final owner authorization packet exists;
- no exact approved implementation commit is named;
- no exact maintenance window is named;
- stale MCP rows can still attach to the store being migrated;
- aio2 is still a 384-era live store when the window expects dual-node cut-over;
- aio2 or Mac model core file hashes differ;
- Mac direct-SQL profile and continuity-report discrepancy are not explicitly
  accepted or remediated;
- DB, WAL, SHM, or binary backups are missing;
- `doctor --json` has fails on either node;
- copied-DB probe is not green;
- preflight under `--live-cutover --strict` is not green for the node being
  migrated;
- rollback operator and rollback packet are not named.

## Owner Questions

1. Accept `33d55e0e5e0ee61fd7d248f0be8aea55a1d2ddd7` as the proposed
   implementation/proposal baseline, or choose a different commit.
2. Accept `atomic_node_cutover_only`, or request a separate mixed-reader proof.
3. Decide whether Mac's migrated state is accepted after stale-reader cleanup,
   with continuity-report follow-up tracked separately, or whether Mac needs a
   rollback/backup review before final acceptance.
4. Name maintenance window and write-freeze policy.
5. Name rollback owner.
6. Decide whether inactive/stale rows are left untouched or migrated later.

## Current Recommendation

Recommended next owner action:

```text
ACCEPT_PROPOSAL_AS_DRAFT_ONLY / REQUEST_FINAL_AUTHORIZATION_PACKET / LIVE_GTE_NO_GO
```

Recommended next implementation action after owner accepts the draft:

```text
write final authorization packet with exact window, backups, binary hashes,
Mac stale-reader cleanup evidence, aio2 migration decision, rollback owner, and
go/no-go checkboxes
```
