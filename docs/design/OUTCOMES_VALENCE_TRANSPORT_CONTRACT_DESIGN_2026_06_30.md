# Outcomes→Valence Transport Contract — Design-Only De-Risk (arc5)

> Status: **design only**. The single read-only producer in §2 is the *only* thing
> implementable now (it builds and is fully verifiable here); §3–§6 are
> specification, not code. Throughout, valence is **derived in shadow**, never
> **produced** into any durable state. All write/learning/influence surfaces remain
> owner-gated FALSE.
>
> Repo: `/Data/CascadeProjects/agent-bridge` @ branch `feat/scope-survey-diagnostic`.
> Crates touched (only): `ab-store` + `ab-bridge` (both build here; `ab-seed-bridge`
> is unbuildable in this env per the MEASURE build caveat — it needs an unreachable
> `seed_neuron` git dep).
>
> Provenance: this document was produced by a MEASURE-first survey (4 parallel
> read-only repo agents) + a 3-approach design panel + 3 adversarial verifiers
> (safety-boundary / buildability / ceiling-honesty). All three verifiers returned
> `sound_with_fixes`; their fixes (the `tags` column name, the boundary echoes, the
> de-decorated frontier section, the two-consumer disambiguation) are applied below.

---

## 1. Problem statement — the MEASURE-corrected honest truth

The roadmap framed arc5 as "build the valence→learning **channel**." The ground-truth
MEASURE relocates the frontier **one step earlier**: the body emits an honest
**outcome-record** stream, but the **derivation** of a valence scalar/vector from that
stream is **unbuilt**.

- **Supplier side — derivation is UNBUILT, raw material is rich and honest.** Outcomes
  are ingested as `MemoryRecord` with `importance = 0.5` **HARDCODED**
  (`crates/bridge/src/present_ingest.rs:240`, `fn build_outcome_memory`). No scalar
  reward / salience / valence is derived from outcomes anywhere. What *does* exist is
  an honest record stream — intent → action → `verify_status` → decision + tags
  (`verify:rendered_ok`, `method:browser_eval`, `decision:approved`) — surfaced
  read-only via `present_outcomes` (`crates/bridge/src/mcp_tools.rs:10836`), the
  `lswr_outcome_admissions` ladder (E2 classify `:10927` → E3 dry_run `:11019` → E4b/c
  approval_packet `:11142` → E4d write_preflight `:11311` → E4 ingest `:11554`, the
  only write, approval-gated, `first_slice_max=1`), and `outcomes_memory_drift`
  (`:11931`). `memory_retrieval_feedback` (`:21684`) writes feedback rows but does
  **not** recompute importance — observational, not a valence driver. **NET: the body
  produces honest outcome records, not a valence signal. The missing first link is
  DERIVATION (outcome metadata → scalar/vector valence).**

This produces **two independent blockers** on a live valence channel:

- **Blocker A — CONSUMER IS HARD-GATED (policy / authority).** The capability ledger
  (`crates/bridge/src/biocortex_capability_ledger.rs`,
  `fn consume_biocortex_capability_ledger()` ~`:232`) runs 17 hard checks; **7 are
  HARD_FALSE on every mutation/learning surface**: `runtime_authority_granted`,
  `executor_enabled`, `adapter_mutation_api_exposed`, `ab_memory_mutated`,
  `retrieval_order_mutated`, `language_generated`, `cognition_claimed`. The one *true*
  boundary requirement is `valence_is_supplied_world_interface = TRUE`: the ledger
  treats valence as an **external input SUPPLIED by the body/world-interface**;
  biocortex only **CONSUMES** it. **AB is the supplier — but the supplier's derivation
  step is itself unbuilt (see supplier side above).** The only write-like op is
  `biocortex_opt_in_apply_side_signal()` (`crates/store/src/lib.rs:625`) — an
  alpha-blended retrieval rerank with externally-supplied scores, gated behind
  `per_call_opt_in + runtime_enabled + may_change_search_order`, **all DEFAULT FALSE**
  (`store/lib.rs:604-609`), and **never called from any runtime path** (its only
  non-test caller is itself a gated shadow surface, `biocortex_shadow.rs:7490`).

- **Blocker B — CONSUMER IS CEILING-BOUNDED (capability / physics of the sibling).** In
  the sibling repo `biocortex-rs`, **two plasticity axes are saturated**: S14 vector
  neuromodulation (weight axis) complete; threshold homeostasis axis closed. **No new
  plasticity axis exists to consume valence ⇒ no live consumer.** This is the hard
  ceiling: a valence consumer cannot exist until a *new* plasticity axis opens in
  biocortex.

**The honest joint statement.** Blocker A is removable from inside this repo via the
owner-gate ladder (reversible). Blocker B is removable **only** from the sibling repo
and gates the final runtime stage. Both must lift, in that order, for a live channel
to exist. The genuine, buildable frontier is therefore **derivation in shadow** —
upstream of where the roadmap located the channel.

---

## 2. The ONE buildable-now artifact — `outcome_valence_shadow` (read-only derivation dry-run)

A read-only MCP tool that **projects** a candidate valence from the already-normalized
outcome metadata, mirroring `embedding_quant_shadow`
(`crates/bridge/src/mcp_tools.rs:28524`) and `memory_scope_survey` (`:28222`) exactly.
It writes nothing, never recomputes the stored `importance=0.5` (`present_ingest.rs:240`),
never touches biocortex, never reranks retrieval. It reads only the
`verify:`/`method:`/`decision:`/`embody:` tag facets that `build_outcome_memory`
writes (~`present_ingest.rs:210-227`) — **not** the embedded content JSON — and emits
**only sha256-hashed keys**.

### 2.1 Tool wiring

- **Struct**: `OutcomeValenceShadowTool { hub: Hub }` with `new(hub)`, placed adjacent
  to `MemoryScopeSurveyTool` (`mcp_tools.rs:28240`). `name() -> "outcome_valence_shadow"`;
  no-param `schema()` (`input_schema["type"]=="object"`, no properties);
  `async execute(&self, args, ctx) -> Result<ToolResult>` returning
  `ToolResult::json_text(&json!({…}))`, or `ToolResult::error("no memory store configured")`
  when `self.hub.store` is `None`.
- **Register**: `reg_if(&mut reg, policy, Tier::Standard, Arc::new(OutcomeValenceShadowTool::new(hub.clone())))`,
  right after the `EmbeddingQuantShadowTool` registration.
- **Deps**: only `ab-store` (new read-only method + struct) + `ab-bridge` (tool).
  `sha2` is already a workspace dep used for hashed keys. No `seed-bridge`, no
  biocortex crate, no new dependency.

### 2.2 Exact JSON envelope

```jsonc
{
  "schema": "agent_bridge.outcome_valence_shadow.v0",
  "read_only": true,
  "boundary": {
    "mode": "valence_derivation_dry_run",
    "read_only": true,
    "mutates_ab_memory": false,
    "recomputes_stored_importance": false,
    "writes_valence": false,
    "changes_memory_search_order": false,
    "runs_biocortex": false,
    "supplies_to_biocortex": false,
    // echoes of the capability-ledger hard-false dimensions this tool sits adjacent
    // to, so the envelope is self-auditing against biocortex_capability_ledger.rs
    "runtime_adapter_approved": false,
    "executor_enabled": false,
    "runtime_authority_granted": false
  },
  "rule": {
    "schema": "agent_bridge.outcome_valence_rule.v0",
    "note": "Transparent deterministic map (verify_status, decision) -> base valence, scaled by a method-confidence factor. No model, no learning, no randomness. See §2.4.",
    "valence_range": [-1.0, 1.0],
    "method_confidence_factors": {
      "browser_eval": 1.0, "macos_ax_verify": 1.0, "desktop_verify": 0.9,
      "lite_probe": 0.7, "self_report": 0.5, "unknown": 0.6
    }
  },
  "summary": {
    "present_outcome_rows": 128,
    "derivable_rows": 121,
    "non_derivable_rows": 7,
    "coverage": 0.945313,
    "mean_valence": 0.412000,
    "min_valence": -0.900000,
    "max_valence": 1.000000,
    "positive_rows": 104,
    "neutral_rows": 9,
    "negative_rows": 8
  },
  "distribution": [
    { "bucket": "[-1.0,-0.5)", "rows": 5 },
    { "bucket": "[-0.5, 0.0)", "rows": 3 },
    { "bucket": "[ 0.0, 0.5)", "rows": 21 },
    { "bucket": "[ 0.5, 1.0]", "rows": 92 }
  ],
  "facet_breakdown": {
    "by_verify_status": [ {"verify_status":"rendered_ok","rows":110}, {"verify_status":"failed","rows":6}, {"verify_status":"","rows":5} ],
    "by_decision":      [ {"decision":"approved","rows":98}, {"decision":"rejected","rows":7}, {"decision":null,"rows":23} ],
    "by_method":        [ {"method":"browser_eval","rows":80}, {"method":"self_report","rows":12} ]
  },
  "rows": [
    {
      "key_sha256": "9f2c…(64 hex)…",
      "scope_sha256": "11ab…(64 hex)…",
      "verify_status": "rendered_ok",
      "decision": "approved",
      "method": "browser_eval",
      "embody": "embodied",
      "derivable": true,
      "valence": 1.000000,
      "valence_class": "positive",
      "rule_path": "verify=rendered_ok+decision=approved -> base=+1.0 * conf(browser_eval=1.0)"
    },
    {
      "key_sha256": "7d01…",
      "scope_sha256": "0000…",
      "verify_status": "",
      "decision": null,
      "method": "unknown",
      "embody": null,
      "derivable": false,
      "valence": null,
      "valence_class": "non_derivable",
      "rule_path": "no verify_status and no decision -> not derivable"
    }
  ],
  "non_goals": [
    "Does NOT write or recompute the stored importance=0.5 (present_ingest.rs:240).",
    "Does NOT persist valence to any column or sidecar.",
    "Does NOT supply valence to biocortex (no live plasticity axis consumes it — ceiling, Blocker B).",
    "Does NOT change retrieval order or call memory_search.",
    "Not a learned reward model — a transparent deterministic rule only.",
    "Not a credit-assignment engine — emits per-record terminal valence with an attribution facet, not multi-step transport."
  ],
  "owner_decision_packet": {
    "approval_packet": true,
    "read_only": true,
    "authorized": false,
    "decision": "valence_derivation_enablement",
    "writes_authorized": false,
    "gate_note": "Deriving a PERSISTED valence signal (let alone supplying it to biocortex or letting it influence importance/retrieval) is owner/board-gated. This tool only PROJECTS a candidate valence; it authorizes nothing. A flip requires (1) a reviewed derivation rule, (2) explicit owner approval, (3) a downstream consumer (new biocortex plasticity axis) that does not yet exist.",
    "review_target": { "reviewer": "owner", "commit": "<HEAD>", "forum_post_id": null, "memory_key": "outcome_valence_shadow_v0" },
    "evidence": { "present_outcome_rows": 128, "derivable_rows": 121, "coverage": 0.945313, "mean_valence": 0.412 },
    "rollback": "No state changes to roll back — read-only projection."
  }
}
```

Empty corpus → `summary.present_outcome_rows=0`, `coverage=0.0`, `mean_valence=0.0`,
`rows=[]`, `read_only=true` (honest vacuous case, like
`embedding_quant_shadow_empty_store_is_no_corpus`).

### 2.3 StateStore method + SqliteStore SQL

**`OutcomeMetaRow` struct** (add near `EmbeddingQuantRow`, `crates/store/src/lib.rs`):

```rust
/// One active `present_outcome` row's already-normalized metadata facets,
/// read-only for the `outcome_valence_shadow` derivation diagnostic. Source
/// fields are the `verify:`/`method:`/`decision:`/`embody:` tags that
/// `build_outcome_memory` writes (present_ingest.rs); NO free-text content is
/// read. `tags_json` holds the raw JSON-array TEXT from the `tags` column; the
/// caller decodes it with serde_json.
#[derive(Debug, Clone)]
pub struct OutcomeMetaRow {
    pub key: String,
    pub scope: Option<String>,
    pub tags_json: String,
}
```

**Trait method** (add by `memory_scope_counts`, `crates/store/src/lib.rs`,
default-empty for non-SQLite parity):

```rust
/// Read-only snapshot of active `kind='present_outcome'` rows' metadata
/// (key, scope, tags) for the `outcome_valence_shadow` valence-derivation
/// diagnostic. Reads only normalized tag facets — never the content body.
/// Mutates nothing; default impl returns empty.
async fn active_outcome_meta_rows(&self) -> Result<Vec<OutcomeMetaRow>> {
    Ok(Vec::new())
}
```

**SqliteStore impl** (add by `active_embedding_quant_rows`,
`crates/store/src/sqlite.rs`) — **note the column is `tags`, not `tags_json`**
(`sqlite.rs:122` `tags TEXT NOT NULL DEFAULT '[]'`; every canonical read uses `tags`,
e.g. `sqlite.rs:1134`):

```rust
async fn active_outcome_meta_rows(&self) -> Result<Vec<crate::OutcomeMetaRow>> {
    let rows = self
        .conn
        .call(move |c| -> RusqliteResult<Vec<crate::OutcomeMetaRow>> {
            let mut stmt = c.prepare(
                "SELECT key, scope, tags \
                 FROM memories \
                 WHERE status = 'active' AND kind = 'present_outcome'",
            )?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(crate::OutcomeMetaRow {
                        key: row.get::<_, String>(0)?,
                        scope: row.get::<_, Option<String>>(1)?,
                        tags_json: row
                            .get::<_, Option<String>>(2)?
                            .unwrap_or_else(|| "[]".to_string()),
                    })
                })?
                .collect::<RusqliteResult<Vec<_>>>()?;
            Ok(rows)
        })
        .await
        .map_err(|e| Error::Backend(format!("active_outcome_meta_rows: {e}")))?;
    Ok(rows)
}
```

The `kind` literal `'present_outcome'` matches `OUTCOME_MEMORY_KIND`
(`present_ingest.rs:56`). Tool-side: decode `tags_json` with
`serde_json::from_str::<Vec<String>>` (same as `sqlite.rs:1147`), split each tag on
the first `:`, pick the `verify`/`method`/`decision`/`embody` prefixes, then compute
`sha256(key)` and `sha256(scope.unwrap_or(""))`. **No raw key/scope ever leaves the
process.**

### 2.4 Deterministic valence rule (transparent, no model, no learning)

Base valence from `(verify_status, decision)`, scaled by a method-confidence factor
(magnitude from method/confidence). Range `[-1.0, 1.0]`. Grounded fields are exactly
the `verify:`/`method:`/`decision:`/`embody:` tag facets that `build_outcome_memory`
writes (~`present_ingest.rs:210-227`) — never the content body.

| verify_status | decision | base | meaning |
|---|---|---|---|
| `rendered_ok` | `approved` | **+1.0** | verified AND owner-approved |
| `rendered_ok` | `null` | **+0.6** | verified, no decision yet |
| `rendered_ok` | `rejected` | **−0.4** | rendered but owner rejected (display ≠ intent) |
| `failed`/`error` | `approved` | **−0.2** | approved despite verify failure (mild contradiction) |
| `failed`/`error` | `rejected` | **−1.0** | failed AND rejected |
| `failed`/`error` | `null` | **−0.7** | failed, no decision |
| `` (empty) | `approved` | **+0.3** | approved, unverified |
| `` (empty) | `rejected` | **−0.6** | rejected, unverified |
| `` (empty) | `null` | **non_derivable** (`valence=null`) | no signal at all |
| any other | `approved` | **+0.3** | unknown-status approval |
| any other | `rejected` | **−0.5** | unknown-status rejection |
| any other | `null` | **non_derivable** | insufficient signal |

**Final valence** = `clamp(base * method_confidence_factor[method], -1.0, 1.0)`.
Negative bases are also scaled (a low-confidence failure is a weaker negative), keeping
the rule monotone and symmetric. `valence_class` = `positive` (>0.05) /
`neutral` (|v|≤0.05) / `negative` (<−0.05) / `non_derivable`. `rule_path` is emitted
per row for full auditability — the "attribution path" the credit-assignment frontier
requires (§5).

### 2.5 Test plan

All in `crates/bridge/src/mcp_tools.rs` `#[cfg(test)]`, using
`mk_test_hub_with_store()` and `result_json()`.

1. **`outcome_valence_shadow_derives_from_facets`** — seed via `store.memory_save`
   three `present_outcome` rows, **each with a DISTINCT scope** (mirror
   `outcome_scope(artifact_id) = Some(format!("outcome:{id}"))`, `present_ingest.rs:71`)
   so the same-kind+same-scope contradiction detector (`sqlite.rs:3394-3438`) cannot
   supersede the cohort before the tool reads them: a
   `[verify:rendered_ok, decision:approved, method:browser_eval]` row, a
   `[verify:failed, decision:rejected]` row, and a bare no-facet row. Assert
   `schema=="agent_bridge.outcome_valence_shadow.v0"`; approved+rendered_ok →
   `valence==1.0`, `valence_class=="positive"`; failed+rejected → `valence==-1.0`;
   bare row → `derivable==false`, `valence==null`; `summary.derivable_rows==N-1`;
   `coverage` correct; distribution buckets sum to `derivable_rows`.
2. **`outcome_valence_shadow_boundary_all_false`** — assert every boundary flag false:
   `mutates_ab_memory`, `recomputes_stored_importance`, `writes_valence`,
   `changes_memory_search_order`, `runs_biocortex`, `supplies_to_biocortex`,
   `runtime_adapter_approved`, `executor_enabled`, `runtime_authority_granted`; plus
   `boundary.read_only==true`, `owner_decision_packet.authorized==false` and
   `writes_authorized==false`.
3. **`outcome_valence_shadow_redaction_grep`** — seed a row with raw key
   `outcome_SECRETARTIFACT123` and a recognizable scope; serialize and assert
   `!s.contains("SECRETARTIFACT123")` and `!s.contains(raw_scope)` — only `*_sha256`
   fields appear.
4. **`outcome_valence_shadow_empty_store`** — no rows → `summary.present_outcome_rows==0`,
   `coverage==0.0`, `rows==[]`, `read_only==true`.
5. **`outcome_valence_shadow_schema_exposes_no_params`** — `schema().name=="outcome_valence_shadow"`,
   `input_schema["type"]=="object"`, no params.

---

## 3. The transport contract schema — `ab.valence_transport.v1` (specification, not built)

This is the **output type of the missing derivation step** — producer-agnostic and
consumer-agnostic. It says *what a valence record is once computed*, so the derivation
rule (§2.4, versioned `ab.valence_derivation.v0`) and the not-yet-existing consumer can
each be built and versioned independently against a stable type. It is a **dormant data
contract**: writable to a shadow store, readable by a dry-run, never wired to retrieval
or biocortex. It reuses the real arc3 pattern in `crates/memory-columnar/src/lib.rs` —
a `SCHEMA_CONTRACT_META_KEY` in the Parquet footer plus `verify_contract()` (`:392`)
that **rejects an incompatible file before decoding any row group**.

### 3.1 Record shape (one valence event)

```jsonc
{
  "schema": "ab.valence_transport.v1",
  "read_only": true,
  "boundary": {
    "is_world_interface_supply": true,   // the ONE true flag: valence is supplied, not actioned
    // full enumeration of the capability-ledger hard-false field names, so an audit
    // can prove no record was produced under an unauthorized boundary:
    "ab_memory_mutated": false,
    "retrieval_order_mutated": false,
    "adapter_mutation_api_exposed": false,
    "runtime_authority_granted": false,
    "executor_enabled": false,
    "language_generated": false,
    "cognition_claimed": false,
    "runs_biocortex": false
  },
  "valence_id": "sha256:…",              // sha256(producer_schema|outcome_artifact_id|attribution_target)
  "attribution": {
    "target_kind": "memory_key",         // enum: memory_key | action_tool_call | segment | episode
    "target_hash": "sha256:…",           // hashed memory key / tool-call id credit assigns TO
    "outcome_artifact_hash": "sha256:…", // hashed <id>.outcome.json source record
    "path_depth": 1                      // hops from terminal outcome to target (credit-trace length)
  },
  "granularity": "step",                 // enum: token | segment | step | turn | episode
  "signal_class": "outcome",             // enum: process | outcome
  "magnitude": 0.73,                     // f32, UNSIGNED |credit|, range [0,1]
  "sign": -1,                            // i8 in {-1,0,+1}; magnitude×sign = signed valence
  "confidence": 0.88,                    // f32 [0,1]; producer's certainty in this assignment
  "source_verifier": "verify_status_rule", // enum: verify_status_rule | decision_rule | process_rule | composite
  "method_family": "model_based",        // enum: monte_carlo | temporal_difference | model_based | game_theoretic | information_theoretic
  "fusion_role": "outcome_anchor",       // enum: process_step | outcome_anchor | fused_pair_pos | fused_pair_neg
  "audit": {
    "producer_schema_version": "ab.valence_derivation.v0", // DERIVER version, distinct from transport version
    "produced_at": 1780000000,
    "ledger_boundary_echo": "biocortex.capability_ledger.v3",
    "owner_decision_packet": { "authorized": false, "forum_link": null, "reviewer": null, "commit": null }
  },
  "non_goals": [
    "does_not_trigger_learning", "does_not_rerank_retrieval",
    "does_not_mutate_importance", "not_a_reward_for_any_live_policy"
  ]
}
```

**Load-bearing design notes.**
1. `magnitude` unsigned + separate `sign`: a `sign=0` record is a *visited-but-neutral*
   credit assignment, distinct from "no record" — which a single signed float cannot
   express.
2. `attribution.path_depth` carries the credit-assignment *trace length*, satisfying
   the requirement to carry an attribution path, not just a terminal scalar.
3. `producer_schema_version ≠ contract version`: the transport type (`v1`) is stable
   while the derivation rule iterates; a consumer reads `producer_schema_version` to
   decide how to *weight* a record, not whether it can *decode* it.
4. **`ledger_boundary_echo` is a verified field, not a decorative one** (see §3.3
   rule 1b): a reader checks `ledger_boundary_echo` equality against the
   capability-ledger version in force **before trusting `owner_authorized`**, so a
   record produced under a later/different boundary cannot be silently mis-read as
   authorized-under-the-current-boundary.

### 3.2 Columnar layout (sibling Parquet table, mirrors `MemoryColumnarRow`/`arrow_schema()`)

Flat columns (no nested structs) so a non-Arrow reader can decode and `verify_contract`
can reject before any row group is touched. Footer KV:
`ab.schema_contract = "ab.valence_transport.v1"`, `ab.read_only = "true"`,
`ab.boundary_echo = "biocortex.capability_ledger.v3; valence_is_supplied_world_interface=true"`.

| # | column | Arrow type | notes |
|---|--------|-----------|-------|
| 0 | `valence_id` | `Utf8` | sha256 hex, primary key |
| 1 | `attribution_target_kind` | `Utf8`(dict) | enum |
| 2 | `attribution_target_hash` | `Utf8` | hashed |
| 3 | `outcome_artifact_hash` | `Utf8` | hashed source |
| 4 | `attribution_path_depth` | `Int32` | ≥0 |
| 5 | `granularity` | `Utf8`(dict) | enum |
| 6 | `signal_class` | `Utf8`(dict) | process \| outcome |
| 7 | `magnitude` | `Float32` | [0,1] |
| 8 | `sign` | `Int8` | {-1,0,+1} |
| 9 | `confidence` | `Float32` | [0,1] |
| 10 | `source_verifier` | `Utf8`(dict) | enum |
| 11 | `method_family` | `Utf8`(dict) | enum |
| 12 | `fusion_role` | `Utf8`(dict) | enum |
| 13 | `producer_schema_version` | `Utf8`(dict) | deriver version |
| 14 | `produced_at` | `Int64` | unix secs |
| 15 | `ledger_boundary_echo` | `Utf8`(dict) | ledger version echo (verified before trust) |
| 16 | `owner_authorized` | `Boolean` | always `false` at v1 |

Low-cardinality columns (1,5,6,10–13,15) are dictionary-encoded for cheap scan-by-enum
(the natural consumer query: "all `outcome`-class, `sign=−1` records over window W").
The JSON `audit.owner_decision_packet` collapses to a single `owner_authorized` boolean
in columnar form (other packet fields NULL-by-construction until a gate flips); the full
packet lives only on the JSON surface, and `owner_authorized` is only trusted **after**
the `ledger_boundary_echo` check (§3.1 note 4).

### 3.3 Evolution rules (lifted from the verified `memory-columnar` discipline, `lib.rs:46-49,103-104,392-409`)

1. **Footer-or-header contract id, verified before decode.** Every reader calls
   `verify_contract()` against `SCHEMA_CONTRACT_META_KEY` *before* reading any row
   group; a mismatch is `Err(Contract{expected,found})` — the file is **rejected, not
   best-effort parsed**. The JSON surface mirrors this: read top-level `"schema"`
   first, bail on mismatch.
   - **1b. Boundary echo verified before trusting authorization.** In addition to the
     schema id, a reader checks `ledger_boundary_echo` equality against the
     capability-ledger version it expects, **before** acting on `owner_authorized`.
     A record whose echo does not match the current ledger is treated as
     unauthorized-by-construction regardless of its `owner_authorized` bit. This is the
     audit-proof tie between a record and the boundary in force when it was produced.
2. **Append-at-end only, within a major.** New columns/fields are added at the end with
   a safe default (`NULL`/`0`/`false`); readers ignore unknown trailing columns or fill
   missing tails with defaults. No reorder, no retype of an existing column.
3. **Rename / retype / semantics-change ⇒ MAJOR bump** (`v1→v2`). Old consumers then
   reject rather than mis-read.
4. **Enum widening = minor; enum re-meaning = major.** Adding `granularity:"multi_agent"`
   is append-compatible (old reader routes the unknown dict value to a required
   `unknown` bucket). Redefining `"step"` is a major.
5. **`producer_schema_version` evolves independently and is never gated by transport
   version** — the deliberate decoupling (§3.1 note 3). Consumers treat it as a
   *trust/weight* input, not a *decodability* input.
6. **A lock-test pins the column set** (mirror `arrow_schema_is_stable`): a unit test
   asserts the exact ordered column list + the contract string, so an accidental
   reorder fails CI before shipping a silently-incompatible file.

---

## 4. Governance boundary map + gate ladder

### 4.1 Boundary diagram (every existing gate located on it)

```
 SUPPLIER  =  AGENT-BRIDGE (the "body" / world-interface)        │ TRANSPORT CONTRACT │   CONSUMER = BIOCORTEX (sibling repo)
════════════════════════════════════════════════════════════════╪════════════════════╪═══════════════════════════════════════
 [RAW MATERIAL — honest, built]                                   │                    │
   outcome.json sidecars (intent→action→verify_status→decision)  │                    │
   present_outcomes            mcp_tools.rs:10836  (read-only)    │                    │
   outcomes_memory_drift       mcp_tools.rs:11931  (read-only)    │                    │
        │  build_outcome_memory  present_ingest.rs:240            │                    │
        ▼  importance = 0.5  ◀── HARDCODED. NO DERIVATION. ───────┼── ❶ MISSING LINK   │
   [DERIVATION — UNBUILT → §2 shadow projects it]                 │   (arc-5 frontier) │
        │                                                         │                    │
 [INGEST LADDER — built, owner-gated]                             │                    │
   lswr_outcome_admissions  E2 classify  :10927  read-only        │                    │
        │                   E3 dry_run    :11019  read-only        │                    │
        │                   E4b/c packet  :11142  OWNER            │                    │
        │                   E4d preflight :11311  OWNER            │                    │
        ▼                   E4  ingest    :11554  ◀ ONLY WRITE (approval+token, first_slice_max=1)
   AB MEMORY (MemoryRecord)                                       │                    │
        │                                                         │                    │
 [INFLUENCE / TRANSPORT — built shells, all DEFAULT-FALSE]        │                    │
   memory_biocortex_t6_influence_gate   mcp_tools.rs           ───┼── ❷ T6 GATE        │
   biocortex_opt_in_apply_side_signal   store/lib.rs:625    ──────┼── ❸ SIDE-SIGNAL ───┼──▶ alpha-blend RERANK
     gates (DEFAULT FALSE, store/lib.rs:604-609):                 │  NEVER called from │    (externally-supplied
       per_call_opt_in · runtime_enabled                         │  any runtime path  │     scores; tests/CLI only)
       runtime_adapter_approved · may_change_search_order        │                    │
 [STATIC LEDGER — the boundary contract itself]                   │                    │
   consume_biocortex_capability_ledger   biocortex_capability_ledger.rs:232            │
     ❹ 7 HARD-FALSE: runtime_authority_granted · executor_enabled                      │
        adapter_mutation_api_exposed · ab_memory_mutated · retrieval_order_mutated     │
        language_generated · cognition_claimed                                         │
     ❺ BOUNDARY requirement: valence_is_supplied_world_interface = TRUE                │
 [RATIFICATIONS] Forum #120 (scope flip, prod writes=false) · Forum #102 (opt-in)      │
════════════════════════════════════════════════════════════════╪════════════════════╪═══════════════════════════════════════
                                                                                       ▼
                                                          CEILING ❻: biocortex plasticity TWO AXES SATURATED
                                                          (S14 vector neuromod · threshold homeostasis closed)
                                                          → NO axis to consume valence → NO live consumer
```

The pipeline is gated **twice over**: every transport surface (❷❸) is policy-default-false
*and* the only thing it could feed (❻) does not exist. The single TRUE boundary flag (❺)
is what makes a **supplier-side** derivation legitimate: biocortex is contractually a
consumer of an external signal, so building derivation in AB does not violate the
consumer's boundary.

### 4.2 Gate ladder

| # | Stage | Label | Governing / mirrored gate | What it does |
|---|-------|-------|---------------------------|--------------|
| **V0** | Valence-derivation shadow producer (= **§2**) | **buildable-now** | mirrors `embedding_quant_shadow` (`mcp_tools.rs:28524`) + `memory_scope_survey` (`:28222`) | `outcome_valence_shadow.v0`: derives a **candidate** valence from `verify_status`+`decision`+`method`; projection only; writes nothing; `importance` stays 0.5. |
| **V1** | Dry-run transport projection | **buildable-now** | mirrors `lswr_outcome_admissions_dry_run` (`:11019`) + `biocortex_opt_in_dry_run` | Read-only `valence_transport_dry_run.v0`: projects what a `ab.valence_transport.v1` side-signal payload *would* contain (`biocortex_opt_in_apply_side_signal` shape, `store/lib.rs:625`) — candidate keys, scores in `[-1,1]`, coverage vs threshold. Calls nothing live. |
| **V2** | Owner review packet | **owner-gated** | mirrors `lswr_outcome_admissions_approval_packet` (`:11142`) + T6 envelope | `valence_channel_review_packet.v0`: bundles V0+V1 evidence into the decision-packet envelope, `not_authorized[]` exhaustive, `review_target{reviewer,commit,forum_post_id,memory_key}`. Requests a human; authorizes nothing. |
| **V3** | Owner decision record | **owner-gated** | mirrors `memory_biocortex_t6_candidate_expansion_owner_decision_record` + Forum #120/#102 | Records the signed verdict. Even on approve, can unlock only the **next read-only gate** — never a production write. |
| **V4** | Runtime influence | **ceiling-blocked** | `biocortex_opt_in_apply_side_signal` runtime gates (`store/lib.rs:604-609`) **AND** ledger ❹/ceiling ❻ | Live alpha-blend rerank consuming valence. Blocked **not by policy alone**: even with `runtime_enabled=true` + owner approval, **no consumer plasticity axis exists** to make valence change anything durable (Blocker B). |

**Critical ladder property:** V0–V3 are fundable inside AB today in strict mirror of two
already-merged ladders. **V4 is a double wall** (owner-gate *and* ceiling), which is why
the ladder is honest rather than aspirational.

---

## 5. Frontier alignment (why each field exists)

Each transport field stands on an **internal design rationale** first; the external
research below is *illustrative corroboration* from a 2026 web survey done while writing
this design, not a load-bearing dependency. The schema does not require any specific
paper to exist, and no field's correctness depends on a citation.

| field | internal rationale (load-bearing) | illustrative external corroboration |
|---|---|---|
| `granularity {token,segment,step,turn,episode}` | A consumer must pick a credit method matched to the record's *resolution* rather than assuming episode-level; the tag makes resolution explicit instead of implicit. | Credit-assignment work distinguishes a granularity axis (token/segment/step/turn) — see the agentic-RL survey below. |
| `method_family {monte_carlo, temporal_difference, model_based, game_theoretic, information_theoretic}` | A consumer that implements one credit method (e.g. TD) reads only the rows it can use; the tag is a *self-description of how the credit was assigned*, not a runtime dependency. | The same surveys organize credit methods by methodology family. |
| `signal_class {process,outcome}` + `fusion_role` | A *process* signal (intermediate step quality) and an *outcome* signal (terminal verdict) must be distinguishable so a consumer can fuse or weight them differently; `verify_status=rendered_ok` is exactly a *programmatic-rule outcome verifier*. `fusion_role` lets a consumer reconstruct positive/negative pairs. | Process-vs-outcome reward fusion is an active 2026 direction (e.g. *Online Process Reward Learning for Agentic RL*, illustrative/unverified arXiv 2509.19199). |
| `magnitude` (unsigned) + `sign` + `confidence` | Densified, signed, uncertainty-aware credit; `confidence` lets a consumer down-weight low-confidence credit, the direct mitigation for mis-calibrated reward. | Mis-calibrated reward functions are widely cited as a top cause of agentic deployment failure (2026 governance commentary). |
| `attribution.{target_kind,target_hash,path_depth}` | Credit must point *at the thing it credits* (a memory op or a tool call), with a trace length — not float into a terminal scalar. `target_kind=memory_key` is the bridge to a memory-operation learner. | Memory-as-RL work treats memory ops as policy actions to be credited (e.g. *Mem-T: Densifying Rewards for Long-Horizon Memory Agents*, illustrative/unverified arXiv 2601.23014; AgeMem, in the autonomous-agent-memory survey arXiv 2603.07670). |
| `audit.{producer_schema_version,produced_at,ledger_boundary_echo,owner_decision_packet}` + `boundary{}` | Audit metadata must span every record so an auditor can prove the boundary in force at production time; the read-only dry-run + owner-gate ladder *is* the governance posture. | Audit-proof, governance-spanning mechanisms are an explicit 2026 expectation. |

### 5.1 Two distinct hypothetical consumers — neither exists, neither lifts the other's ceiling

This transport stream could, in principle, serve **either** of two future consumers.
They are **different**, and confusing them would misstate the ceiling:

- **(a) An in-AB memory-operation learner** — if AB ever grows a policy over memory ops
  (store / retrieve / update / summarize / discard), this stream is its per-action
  credit feed (`attribution.target_kind=action_tool_call` + `granularity=step` for
  per-step credit; `granularity=episode` for the outcome anchor). **This learner does
  not exist today, and — critically — building it would NOT lift Blocker B.** It is a
  *different* consumer living in AB, not the biocortex plasticity sink.
- **(b) A new biocortex plasticity axis** — the consumer the capability ledger's
  `valence_is_supplied_world_interface=true` contract anticipates. **Blocker B is lifted
  only by this**: a new plasticity axis opening in the `biocortex-rs` sibling repo,
  entirely outside AB. No AB ladder, owner decision, or in-AB learner can produce it.

Because **neither (a) nor (b) exists**, the transport schema is specified, not built.
Nothing in AB can "grow the consumer that lifts the ceiling" for the biocortex valence
channel; only the sibling repo can.

---

## 6. Ceiling, non-goals & recommendation

### 6.1 The two-blocker ceiling and what lifts each

- **Blocker A — owner-gate (authority).** Located at the V2→V3 ladder; concretely the
  default-false gates of `biocortex_opt_in_apply_side_signal` (`store/lib.rs:604-609`)
  and the 7 ledger hard-false checks (`biocortex_capability_ledger.rs`, ❹).
  **Lifting event:** an owner decision record (V3), ratified in the Forum #120/#102
  pattern, flipping a specific gate from false — *internal to AB, reversible*. **Scope
  of lift:** unlocks at most the next read-only/trial gate — never a production write by
  itself.
- **Blocker B — saturated-consumer ceiling (capability).** Biocortex's two plasticity
  axes are saturated (S14 vector neuromodulation; threshold homeostasis closed); the
  only extant valence sink is the transient `apply_side_signal` rerank, which is
  retrieval reordering, **not** learning. **Lifting event:** a **new plasticity axis
  opening in the biocortex sibling repo** — entirely outside AB; no AB ladder, owner
  decision, forum ratification, or in-AB learner (§5.1a) can produce it. **Scope of
  lift:** without it, V4 is dead even with full owner approval.

**Both must lift, in that order, for a live valence channel to exist.**

### 6.2 Global non-goals

This design does **not**: write or recompute `importance=0.5` (`present_ingest.rs:240`);
persist valence to any column/sidecar; supply valence to biocortex; change retrieval
order or call `memory_search`; build a learned reward model; or build a multi-step
credit-assignment engine. It introduces a learned reward model nowhere — only a
transparent deterministic rule (§2.4). The transport schema (§3) builds no producer, no
consumer, no writer; all write/learning/influence surfaces remain owner-gated FALSE.

### 6.3 Recommendation — the honest minimum

**BUILD `outcome_valence_shadow` (§2 / ladder stage V0) now; keep everything in
§3–§4.2-V1+ as design-only.**

Rationale:
- **It is the one genuinely-buildable, in-discipline arc5 artifact.** It builds *exactly*
  the single missing first link the MEASURE identifies — derivation (outcome metadata →
  scalar valence) — and nothing past it. It is fully verifiable here (only `ab-store` +
  `ab-bridge`, both build; no `ab-seed-bridge`).
- **It crosses no gate.** Read-only, hashed keys, every boundary flag false,
  `owner_decision_packet.authorized=false`. It mirrors `embedding_quant_shadow` /
  `memory_scope_survey` verbatim, so it inherits a proven, reviewed posture.
- **It makes the rest measurable without overselling.** It quantifies how many of
  today's outcome records would yield a valence record, at what distribution and
  coverage — turning the §3 contract from an assertion into an evidenced projection —
  while honestly labeling the output **derived in shadow**, never **produced**.
- **It stops exactly at the ceiling.** No consumer exists (Blocker B), so V1–V4 are
  deferred by design. Building them now would either be inert (V1) or dishonest (V2+
  implies a path to a consumer that does not exist).

Do **not** advance past V0 in this arc. V1 (transport dry-run) is buildable but inert
until V0 lands and is reviewed; V2+ require an owner decision and, for V4, a sibling-repo
event that no AB work can produce. The honest minimum is: **land the read-only derivation
shadow, keep the transport contract and gate ladder as a reviewed specification, and
re-open arc5 only when a new biocortex plasticity axis creates a real consumer.**
