# RUNBOOK — Track MS two-node (aio2 ↔ mac) wet-test

**Purpose**: validate the MS-3 conflict-aware merge (`VersionVectorMerge`) on the **real** cross-network sync, i.e. run the Phase-1 falsifier on actual hardware rather than the single-machine simulation (`vv_merge_e2e_*` tests).
**What it proves**: two nodes editing the same memory key while offline do **not** lose either edit (no silent last-write-wins drop) — the losing edit is preserved as a non-destructive conflict copy.
**Companion**: design memo `MEMORY_SYNC_VERSION_VECTOR_BORROW_2026_05_24.md`; forum design thread 33.
**Safety**: everything uses the `mstest:` key prefix so production memories are untouched; cleanup at the end purges it.

---

## 0 · Preconditions (BOTH nodes)

On **each** of aio2 and mac:

1. Code at or after `379e46a` (MS-1b-ii + MS-3) — `git -C /path/to/agent-bridge log --oneline -1` includes the MS commits, and `agent-bridge.real` rebuilt + installed from it.
2. Wrapper deployed with `AB_SYNC_NODE` (commit `34e7bc7`):
   ```sh
   AGENT_BRIDGE_SKIP_GITHOOKS=1 bash scripts/wrapper/install.sh
   file ~/.local/bin/agent-bridge            # must say: shell script (NOT ELF)
   grep AB_SYNC_NODE ~/.local/bin/agent-bridge
   ```
3. The MCP server / agent process **relaunched** after the wrapper change (so memory_save runs with `AB_SYNC_NODE` set). Confirm the node identity differs per machine:
   ```sh
   echo "${AB_SYNC_NODE:-$(hostname -s)}"     # aio2 → "aio2"; mac → its hostname
   ```
   The two must be **different strings** (they hash to different node ids).
4. Sync repo healthy on both (`agent-bridge sync -v` runs clean once to establish a common baseline).

> If a node's wrapper is not yet deployed, its writes stay **unstamped** and the merge degrades to the old `NewerWins` (safe, but the conflict-copy behaviour won't trigger — the test would be inconclusive, not failing). Deploy first.

Let `DB=~/.local/share/agent-bridge/state.db` (or `$AGENT_BRIDGE_DB`). All verification queries are **read-only**.

---

## 1 · Test A — disjoint keys merge cleanly (sanity)

1. **aio2**: save a memory `mstest:ka` (content `from-aio2`) via your agent / MCP `memory_save`.
2. **mac**: save a memory `mstest:kb` (content `from-mac`).
3. **aio2**: `agent-bridge sync -v`   → pushes `ka`.
4. **mac**:  `agent-bridge sync -v`   → pulls `ka`, pushes `kb`.
5. **aio2**: `agent-bridge sync -v`   → pulls `kb`.
6. Verify on **both** nodes:
   ```sh
   sqlite3 "$DB" "SELECT key, substr(content,1,20) FROM memories WHERE key LIKE 'mstest:%' ORDER BY key;"
   ```
   **PASS**: both nodes show `mstest:ka` and `mstest:kb`. Sync logs show `conflict_copies=0`.

---

## 2 · Test B — concurrent same-key edit (the core falsifier)

**Goal**: both nodes edit `mstest:shared` after sharing a base, *without* an intervening sync, then sync. The second importer must create a conflict copy, not drop an edit.

1. **aio2**: save `mstest:shared` = `base`.  Then `agent-bridge sync -v` (push base).
2. **mac**:  `agent-bridge sync -v` (pull base). Now both hold `mstest:shared` with the **same** version vector.
   ```sh
   sqlite3 "$DB" "SELECT version_vector FROM memories WHERE key='mstest:shared';"   # same on both
   ```
3. **Diverge — do NOT sync between these two edits:**
   - **aio2**: save `mstest:shared` = `vA`   (bumps the aio2 counter)
   - **mac**:  save `mstest:shared` = `vB`   (bumps the mac counter)
4. **aio2**: `agent-bridge sync -v`   → pushes `vA`.
5. **mac**:  `agent-bridge sync -v`   → pulls `vA`; its vector is **concurrent** with local `vB`.
   - Expect a prominent log line:
     `[sync] ⚠ 1 conflict copy created — concurrent same-key edit(s) preserved …`
6. **Verify on mac** (the receiving node):
   ```sh
   sqlite3 "$DB" "SELECT key, substr(content,1,20), status FROM memories WHERE key LIKE 'mstest:shared%' ORDER BY key;"
   ```
   **PASS** requires ALL of:
   - canonical `mstest:shared` content = **`vB`** (mac kept its own edit — *not* overwritten by `vA`);
   - exactly one row `mstest:shared#conflict-<hex>` with content **`vA`** and `status='conflict'`;
   - **zero rows lost** (both `vA` and `vB` present somewhere).
7. **(Optional) symmetric convergence**: `mac: agent-bridge sync -v` (push, incl. the conflict copy) then `aio2: agent-bridge sync -v` (pull). aio2's local `vA` is concurrent with incoming `vB` → aio2 makes its own conflict copy of `vB`. End state on both nodes: canonical = own edit + a conflict copy of the other → **both versions present on both machines**.

---

## 3 · Decision rule

- **PASS** (Test A clean + Test B preserves both with one conflict copy, zero loss) → MS-3 validated cross-network. Close the "two-node wet-test" gap on thread 33; the data-loss fix is real-hardware-confirmed.
- **FAIL** if any of: an edit silently disappears (LWW drop — the original bug), no conflict copy is created on a concurrent edit, the canonical row gets overwritten by the incoming concurrent edit, or sync errors out. → capture sync `-v` output + the SQL dumps and file on thread 33; do **not** purge the evidence.
- **INCONCLUSIVE** if `version_vector` is empty on the edited rows (a node wasn't stamping — wrapper/AB_SYNC_NODE not active, or process not relaunched). Fix preconditions and rerun.

---

## 4 · Cleanup (both nodes)

```sh
# Remove test rows + conflict copies, then sync so the deletion propagates.
sqlite3 "$DB" "DELETE FROM memories WHERE key LIKE 'mstest:%';"
agent-bridge sync -v
```
(If you used `memory_save`/MCP to create them, you may prefer `memory_delete` per key so tombstones propagate the standard way; the raw DELETE above is fine for a throwaway test prefix.)

---

## Notes

- Stamping covers any write made by a wrapper-launched process. The Stop-hook `agent-bridge sync` is wrapper-launched, so it stamps automatically once §0.2 is done.
- The conflict-copy key is derived from `(key, content, incoming vector)` via FNV, so re-importing the same export is idempotent — re-running a sync will **not** spawn duplicate conflict copies.
- `conflict_copies` now appears in `agent-bridge sync -v` output and is force-surfaced (even without `-v`) whenever > 0.
