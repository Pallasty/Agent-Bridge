# DESIGN — Memory-Sync Hardening: Version Vectors & Conflict Copies (borrow from Syncthing)

**Status**: design draft 2026-05-24. **No code until Phase-1 falsifiers are agreed on the forum.**
**Author**: `aio2:agent-bridge:main#7a37d28e`
**Trigger**: study of `github.com/syncthing/syncthing` (shallow clone read 2026-05-24) against agent-bridge's known memory-sync pain points.
**Forum thread**: design board — *Memory-Sync Hardening — version-vector conflict detection (borrow from syncthing) + P2P later-track*.

---

## 0 · Why this exists (verify-phase output)

agent-bridge memory sync today is **SQLite-as-truth + git-as-transport**:

```
SQLite (truth) → export jsonl → git commit → multi-push (GitLab primary + GitHub mirror)
                                                   ↕ 15-min timer + Stop hook
peer pull → git pull --rebase --autostash → import jsonl → SQLite
```

(see `reference_memory_sync_architecture`, `crates/bridge/src/sync.rs`)

**Known gaps this design targets**:

| Gap | Evidence | Today's blunt fix |
|---|---|---|
| Branch divergence not detected at the git layer; only file conflicts handled | `lesson_sync_fallback_branch_divergence_gap_2026_05_19`; `sync.rs:689-752` | **`reset --hard origin/<branch>`** ("SQLite-as-truth", `sync.rs:743-749`) + 3-fail alert (`b305ff3`/`6e10240`) |
| Conflict resolution is **all-or-nothing at the branch level** — a `reset --hard` discards the loser node's *git* state wholesale; correctness rests entirely on "every prior sync already pushed SQLite" | `sync.rs:724-731` | re-export from SQLite after reset |
| No per-record provenance / concurrency tracking — two nodes editing **the same memory key** independently cannot be distinguished from a clean update | `memories` table has `status` but **no version vector** (`crates/store/src/sqlite.rs:247-250`) | none |
| **The precise record-level data-loss point**: import conflict resolution is **last-write-wins by wall-clock `updated_at`** — the older of two *concurrent* same-key edits is silently dropped | `ImportConflictPolicy::NewerWins` in `plan_import_actions` (`sqlite.rs:1742-1747`: `if r.updated_at > existing { Update } else { Skip }`) | none — this *is* the loss |
| Full-jsonl transport every cycle (no diff) | timer ships whole export | none |

**Core reframe**: move conflict resolution **down from the git-branch layer to the SQLite-record layer**. Once each memory row carries a version vector, jsonl import becomes a **conflict-aware per-key merge**, branch divergence becomes a non-event (git is a dumb pipe), and `reset --hard` (a data-loss-shaped tool) is retired.

Syncthing has solved exactly this problem class (decentralized, multi-writer, conflict-aware, data-loss-averse) and its mechanisms are small and portable.

> **Implementation-audit refinements (2026-05-24, during MS-1 build)**:
> - **The real loss is `NewerWins`, not just `reset --hard`.** The git-layer `reset --hard` is the coarse outer symptom; the precise record-level loss is the LWW tiebreak in `plan_import_actions` (`sqlite.rs:1742`). MS-3 is therefore concretely scoped: **add a `VersionVectorMerge` import policy** that, on an existing key, compares vectors — dominated side takes the winner, **`Concurrent` → conflict-copy (MS-2)** — replacing the wall-clock LWW that drops the loser.
> - **Carry the vector without churning `MemoryRecord`.** jsonl rows are `serde_json::from_str::<MemoryRecord>` and the struct has **~100 literal construction sites**, so adding a field there is high-churn. Instead introduce a sync-boundary `SyncEnvelope { #[serde(flatten)] record: MemoryRecord, #[serde(default)] version_vector: String }` used **only** by `memory_export`/`memory_import`; the vector lives in the SQLite column + this wrapper. Zero construction-site churn.
> - **Node id source**: `crates/bridge/src/sync.rs:823 hostname_short()` (e.g. `aio2`/`mac`) → `node_id_from_name`. Plumb a `node_id` into `SqliteStore` at open so `memory_save` can bump the local counter.

---

## 1 · The borrow (ranked by ROI)

### ⭐ MS-1 — Per-record version vectors (highest ROI)

**Syncthing** (`lib/protocol/vector.go`): each record carries `Vector{ Counters: []Counter{ ID: ShortID, Value: uint64 } }`.
- `Update(id)` bumps `Value = max(counter+1, wall_clock_unix)` — a Lamport counter with a **wall-clock floor**, so values stay monotonic *and* comparable across machines even under clock skew.
- `Compare(b) → Equal | Greater | Lesser | ConcurrentLesser | ConcurrentGreater`. **`Concurrent` = both sides advanced independently = conflict.**
- `Merge(b)` = element-wise max (the clean-merge case).

**Borrow**: add a `version_vector` column to `memories` (and any other synced table). `ID` = **stable node id** (`aio2` / `mac`), *not* per-session sigil — every session on a node bumps that node's counter (mirrors syncthing's device-ID model). On import, `Compare` per key:
- `Greater`/`Lesser` → take the dominant version (clean update);
- `Equal` → no-op;
- `Concurrent` → conflict → MS-2.

> The `max(count+1, now)` trick directly addresses the two-node **serial handoff** (Mac↔aio2): wall-clock floor keeps the vector monotonic across the switch even if a clock is slightly off.

### ⭐ MS-2 — Non-destructive conflict copies + cap (pairs with MS-1)

**Syncthing** (`folder_sendrecv.go:moveForConflict`): the losing version is **renamed, never deleted** → `.sync-conflict-<date>-<modifiedBy>`; a `MaxConflicts` cap prunes the oldest; an already-conflict file is not re-conflicted (no recursion). Crucially, `InConflictWith` (`bep_fileinfo.go:188`) layers a **content check on top of vector concurrency**: if the new version is *based on the content we already hold* (`PreviousBlocksHash == our BlocksHash`), it is **not** a real conflict — suppressing false positives.

**Borrow**: on a `Concurrent` memory conflict, preserve **both** versions — e.g. retain the loser as a `conflict`-status row keyed `<key>#conflict-<node>-<ts>`, surface it on the **incidents** board, and let dream-replay or a human resolve. Cap retained conflict copies per key. Reuse agent-bridge's existing **content/embedding hash** for the syncthing-style false-conflict suppression. This aligns with the existing retire/tombstone state machine and **honors "safe from data loss"** (§5) where `reset --hard` does not.

### MS-3 — Retire `reset --hard`; make divergence a record-level merge

With MS-1+MS-2, the `sync.rs` fallback changes shape: branch divergence no longer triggers `reset --hard origin`. Instead, pull both sides' jsonl, **merge per-key by version vector**, conflict-copy the genuine concurrent edits, re-export, fast-forward. git stops being a correctness boundary.

### MS-4 — Index-diff handshake (lightweight reconciliation)

**Syncthing** (`bep_clusterconfig.go` + `bep_index_updates.go`): peers first exchange a **compact index** (name + version vector + content hash), then request **only** what they lack — full content travels on demand.

**Borrow**: a `(key, version_vector, content_hash)` index exchange over the existing **forum `peer host:port` daemon-http** transport; pull only divergent/missing keys instead of the whole jsonl each cycle. Naturally carries MS-1's vectors → reconciliation *is* conflict detection. (Take the **index-exchange idea only** — see Non-goals on block-level sync.)

### MS-5 — Staggered retention for memory versions / tombstone aging

**Syncthing** (`lib/versioner/staggered.go`): exponential-interval retention — 30 s spacing in the first hour, 1 h in the first day, 1 d in the first 30 days, 1 w in the first year.

**Borrow**: replace the single 7-day cutoff in `dream decay-unused` / `memory_tombstone_aged_archived` with staggered retention — dense recent, sparse old. Cheap "what did memory X look like N days ago" with auto-thinning, instead of binary keep/delete.

### MS-6 — Connection-priority / relay-vs-direct observability (P2P pre-work)

**Syncthing** (`lib/connections/service.go`): every dialer has a `Priority` (lower = better); it dials **all** transports at once and **upgrades relay→direct** when direct becomes reachable (`ConnectionPriorityUpgradeThreshold`). STUN/UPnP/NAT-PMP (`lib/{stun,upnp,pmp}`) do hole-punching — but **under CGNAT they cannot help** (no public mapping).

**Relevance** (`lesson_aio2_cgnat_blocks_tailscale_direct_2026_05_21`): Tailscale **already** implements relay-floor + direct-upgrade (DERP). So the *mechanism* is not the borrow — two things are:
1. **Observability**: expose a relay-vs-direct + latency metric like syncthing's, so "are we on DERP right now?" is *measured*, not merely accepted.
2. **Confirmation**: syncthing's STUN/UPnP being useless under CGNAT **independently validates the agent-bridge diagnosis** — CGNAT is a hard wall, relay is the correct posture, not a failure.

---

## 2 · Phased roadmap (Track MS) — falsifier-first (§6.5 rule 1)

Each phase ships only after its falsifier is agreed and met. Frame-audit-first: read current `sync.rs` + store schema before each implementation step.

### Phase 1 — Conflict-aware sync core (highest ROI, do first)
- **MS-1** version-vector column + `Compare`/`Merge`/`Update` (port the 4 ops; ~one small module + schema migration).
- **MS-2** non-destructive conflict copies + cap + content-hash false-conflict suppression.
- **MS-3** swap the `reset --hard` fallback for record-level merge.
- **Falsifier (Phase 1 PASS/FAIL)**: on two nodes, write *different* keys offline then sync → **both survive** (clean merge, zero conflict copies). Write the *same* key with different content offline on both → **both versions preserved**, exactly one conflict copy surfaced on incidents, **zero rows lost**. FAIL if any write is silently dropped or a spurious conflict fires on a clean base-update.

### Phase 2 — Lightweight reconciliation
- **MS-4** index-diff handshake over daemon-http.
- **MS-5** staggered retention.
- **Falsifier**: index-diff transfers strictly fewer bytes than full-jsonl for an unchanged corpus (→ near-zero), and a single divergent key pulls only that key. Staggered retention keeps the documented density curve and never exceeds the storage budget.

### Phase 3 — P2P track (**LATER / conditional — gated, not scheduled now**)
- **MS-6** relay-vs-direct observability (cheap, can land early as standalone).
- **MS-P2P** full peer-to-peer sync (relay-floor + direct-upgrade + discovery), **only if** Tailscale pain forces it.
- **Activation gate** (per user 2026-05-24): do **not** build P2P now. Start this track only when a concrete Tailscale-pain trigger fires — e.g. sustained DERP-only latency/availability breaching a memory-sync SLO, or a Tailscale outage blocking sync. Until then MS-6 observability is enough to *detect* the trigger.

---

## 3 · Non-goals (do NOT borrow)

- ✗ **Block-level rsync delta sync** (BEP block exchange, Adler-32 rolling hash, `BlocksHash`): built for large files; memory rows are tiny. Take MS-4's *index-exchange* concept only; skip the block machinery.
- ✗ **Full P2P discovery stack** (global discovery server, local UDP beacon `lib/beacon`): agent-bridge already has Tailscale + presence + forum daemon-http.
- ✗ **Encryption / untrusted (receive-encrypted) devices**: agent-bridge runs on a trusted private tailnet. Revisit only if sync ever traverses an untrusted relay.
- ✗ Rewriting the SQLite-as-truth model. Version vectors *strengthen* it (record-level truth) — they do not replace SQLite with a P2P block store.

---

## 4 · Design discipline lifted from Syncthing GOALS.md

Syncthing ranks its goals explicitly: **Safe-From-Data-Loss > Secure > Easy > Automatic > Universal**, and refuses unsafe trade-offs for performance/usability. agent-bridge's memory-sync layer should adopt **"data loss is the overriding failure"** as its first axiom — under that lens the `reset --hard` fallback is wrong-by-construction, which is exactly what MS-2/MS-3 fix.

---

## 5 · Cross-refs

- `reference_memory_sync_architecture` — current SQLite-truth + jsonl-transport + dual-forge mirror + 4-mode recovery
- `lesson_sync_fallback_branch_divergence_gap_2026_05_19` — the gap MS-1/2/3 close
- `lesson_aio2_cgnat_blocks_tailscale_direct_2026_05_21` — CGNAT/DERP context for MS-6 / P2P gate
- `crates/bridge/src/sync.rs` — `run_sync_inner`, the `reset --hard` fallback (`:689-752`), `push_origin_primary_aware` (`c4d9368`)
- `crates/store/src/sqlite.rs` — `memories` schema (target of the version-vector migration)
- Syncthing source (shallow clone `/tmp/syncthing-study`): `lib/protocol/vector.go`, `lib/protocol/bep_fileinfo.go:188 InConflictWith`, `lib/model/folder_sendrecv.go moveForConflict`, `lib/connections/service.go`, `lib/versioner/staggered.go`, `GOALS.md`
