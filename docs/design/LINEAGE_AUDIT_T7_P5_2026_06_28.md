# Lineage / Provenance Audit Predicates (T7 / P5)

**Status:** analyzer landed (read-only); live substrate sparse — see §4.
**Borrow source:** `nexus-civilization/server/core/governance/compliance.py::ComplianceMonitor`
**Code:** `crates/store/src/lineage_audit.rs` (pure module, 12 tests) +
`crates/store/examples/lineage_audit_eval.rs` (read-only eval).
**Scan ref:** `decision_borrowed_patterns_cascade_scan_20260628`,
`docs/design/BORROWED_PATTERNS_BACKLOG_2026_06_28.md` (P5/T7).

---

## 1. What was borrowed

nexus-civilization's `ComplianceMonitor` is the world simulator's "法制院": a
**rule-based, read-only** scanner that reads the append-only event ledger + a
causal DAG and records flags to a governance log — *it never mutates world
state*. It runs five checks each reconciliation cycle; three are general enough
to port to AB's semantic-event spine:

| nexus check | AB predicate | Concept |
|---|---|---|
| `_check_severity_burst` | `severity_burst` | ≥N at/above-floor events in one window, per group → rapid escalation |
| `_check_cascade_depth` | `cascade_depth` | lineage chain depth ≥ limit → runaway / exploit indicator |
| `_check_resource_leak` | `conservation_leak` | a delta with no lineage-traceable admitted entry → un-provenanced mutation |

The two AB-irrelevant checks are **not** ported: `_check_constitutional`
(world-state physics invariants) and `RateAbuseDetection` (per-tick command
rate) have no AB analog.

This is an **idea-level** borrow (Python → Rust, cross-language): the structure
(read-only scan → typed findings → report) and the thresholds (`SEVERITY_BURST_COUNT=4`,
`CASCADE_DEPTH_LIMIT=6`) are carried over; no code is copied.

## 2. Faithful AB mapping

The AB substrate is the `semantic_events` ledger (the SSB typed event spine):
`id, ts, actor, source, action, target, verdict_status ∈ {verified, not_verified,
unknown}, verdict_method, evidence, facts, descriptor`. It is append-only and
node-local, with the "no green laundering" invariant (an inert action is stored
`not_verified`, never a silent success).

The DB-agnostic core operates on a normalized [`AuditEvent`] projection so it is
testable without a DB and reusable over any append-only ledger. The eval maps:

- **group** = `actor` (burst grouping = the producing session).
- **severity** = `verdict_status`: `not_verified` → `Adverse`, `unknown` →
  `Watch`, `verified` → `Benign`.
- **provenance** = `Unprovenanced` iff a `verified` verdict carries **no**
  `evidence` (an effect claimed without traceable proof — the faithful AB analog
  of nexus's "resources grew without a source event"); `Admitted` otherwise. An
  honest `not_verified` is **not** a leak (it declares its own failure).
- **parents** = lineage ids parsed from `facts` JSON keys `parent_event_id` /
  `cause_id` / `parent_ids` / `lineage_ids`; empty when the ledger carries no
  link (the common case today — see §4).

### Reframe legitimacy
`_check_resource_leak` measures conservation at macro scale (total resources
grew >15% with no source event). AB has no conserved-quantity ledger, so a 1:1
port is impossible. The RSI backlog already prescribes the reframe: "any
runtime/config delta with no lineage-traceable admitted entry ⇒ un-provenanced
mutation". `conservation_leak` implements exactly that (un-provenanced effect +
dangling parent reference), which is a legitimate provenance-conservation
analog, not a stretch — it is documented as a reframe, not claimed as identical.

## 3. Discipline

Mirrors `quant` / `coactivation_latch` / `connectivity_repair`:

- **Read-only / report-only.** The core computes findings and writes nothing;
  the eval opens the DB `SQLITE_OPEN_READ_ONLY` and only prints JSON. No writes,
  no MCP tool, **no gate.** The Goal-C RSI doc is explicit — "a continuity
  honest ledger, **NOT** another gate chain" — and the lane's own falsifier
  stops anything that "creates gates that do not feed a dashboard". This lands as
  a report predicate, exactly inside that constraint.
- **Deterministic.** No RNG, no clock, no `HashMap` iteration — `BTree*`
  throughout, every tie broken by id, input processed via a total-canonical-order
  working copy → identical report regardless of row order, even on a degenerate
  duplicate id (tests `report_is_order_independent`,
  `cascade_duplicate_id_is_order_independent`). `cascade_depth` uses an iterative
  Kahn longest-path DP (no recursion → no stack overflow on long chains), with
  depth node-counted (root = 1, one node stricter than nexus's edge-counted
  `chain_depth`).
- **Not true-by-construction.** The predicates fire on synthetic adverse data in
  the 15 unit tests (bursts, deep chains, cycles, un-provenanced effects,
  dangling references) and stay silent on benign data — they test real behavior.

## 4. Honest substrate status (limitation, stated up front)

This is the **analyzer**, not the data. On the surveyed node (2026-06-28) the
spine is dormant:

- `semantic_events`: **3 rows**, all `session/bootstrap` / `verified`, **no**
  lineage links in `facts`.
- `notifications`: 0 rows. `mcp_tool_calls`: 3083, `mcp_tool_errors`: 41 — richer
  telemetry, but lacking the causal/provenance structure the predicates consume.
- The SEPL `resource_versions` lineage substrate (the `b484b70` P0 work) is
  **committed-not-pushed**, awaiting owner review on the #90/L7 lane — it is
  **not** on `master`.

So a live `lineage_audit_eval` run today reports ~0 findings, and the eval prints
the scanned count + how many rows carry a lineage link **so a sparse run is never
mistaken for a clean one**. The value landed now is: (a) the unit-tested,
deterministic predicate library, ready the moment producers populate the spine
(the SSB Object/Affordance contract is an active roadmap area — browser/desktop/
mobile/session producers already emit events; they simply haven't fired much on
this node), and (b) the honest read-only report shape for the Goal-C dashboard.

## 5. Not done / next

- **Wire a real producer's lineage into `facts`.** Once an admission/apply
  producer (e.g. LSWR `verified_outcome_ingestion`) embeds parent/admission ids
  in `facts`, `cascade_depth` and the dangling-reference half of
  `conservation_leak` light up over real data.
- **Goal-C dashboard surface (report-only).** If/when the continuity lane wants
  it, expose the report through the existing dashboard path — **not** a new MCP
  gate.
- Re-run the eval on an active automation node (aio2) where the spine is denser
  to sanity-check thresholds against real adverse bursts.

## 6. Adversarial verification (2026-06-28)

A 2-lens adversarial review (`wf_7fcfd2a9-d74`) ran before landing:

- **Lens A (correctness/determinism)** found 1 blocker + 2 majors, all in the
  original `cascade_depth`: (1) a shared memo cached cycle-shortened depths and
  silently missed real deep chains; (2) recursive `longest_depth` could abort the
  process via stack overflow on a long chain; (3) the order-independence claim was
  false for duplicate ids. All three are fixed: depth is now an iterative Kahn
  longest-path DP (correct for every DAG node regardless of cycles, no recursion),
  and the working copy uses a total canonical sort. New tests pin each fix
  (`cascade_cycle_does_not_hide_a_real_deep_chain`,
  `cascade_deep_chain_does_not_overflow`, `cascade_picks_longer_of_two_parent_branches`,
  `cascade_duplicate_id_is_order_independent`).
- **Lens B (honesty/discipline)** verdict ship-with-fixes: empirically confirmed
  the read-only/no-gate discipline, that the substrate is sparse and honestly
  reported, and that the predicates are not true-by-construction. Its faithfulness
  notes (cascade node-vs-edge "identical" overclaim; severity-burst sliding-window
  reframe; brittle `evidence_present` string check; doc/nit fixes) are all applied.
