//! Retrieval-outcome apply — the behavior-changing consumer of the
//! `retrieval_surfacing` telemetry (surfaced→used), closing the loop the
//! read-only `retrieval_outcome_report` / `retrieval_outcome_shadow` pair was
//! built to calibrate: memories whose surfacings were USED gain importance
//! (+reinforce_step, ceiling-capped), memories surfaced repeatedly but never
//! used lose importance (−decay_step, floor-capped).
//!
//! Design invariants (each carried by a test):
//!
//! 1. **One surfacing, one action.** Every telemetry row is counted toward at
//!    most one reinforce/decay via the v40 `consumed_at` marker. Re-running a
//!    pass immediately is a no-op — pacing comes from evidence accrual, not
//!    from how often the pass runs. Concurrent passes (daemon tick racing a
//!    manual tool pass, possibly cross-process) are safe by construction:
//!    consume-and-write happen in ONE store transaction, consume first, and
//!    the race loser consumes 0 rows and writes nothing.
//! 2. **Below-threshold evidence accumulates.** Keys with `used == 0` and
//!    fewer than `min_surfaced_for_decay` pending surfacings are NOT consumed;
//!    their rows stay pending so a memory surfaced once a day still crosses
//!    the decay threshold eventually instead of losing its signal every pass.
//!    (The ring-cap prune cooperates: it evicts consumed history before
//!    pending evidence.)
//! 3. **Maturation before consumption.** Only rows older than
//!    [`APPLY_MATURATION_SECS`] are eligible — younger rows may still receive
//!    a late `used_at` stamp (memory_get window 1800s, feedback window
//!    [`FEEDBACK_ATTRIBUTION_WINDOW_SECS`]). Maturation is STRICTLY wider
//!    than the widest attribution window, and the stamp UPDATE additionally
//!    guards on `consumed_at IS NULL`, so a stamp can never chase an
//!    already-consumed row even under modest clock skew.
//! 4. **Rollback map before writes.** A confirmed pass persists an audit
//!    memory with every old→new importance BEFORE the first write, mirroring
//!    `outcome_valence_importance_apply` — and re-saves it AFTER the pass
//!    with per-row outcomes, so the map records what actually happened, not
//!    just intent.
//! 5. **No slice lingers silently.** Clamped keys (at ceiling/floor),
//!    zero-step keys (a rule half disabled), orphaned rows (memory no
//!    longer active), and ambient bootstrap rows (mode-excluded from the
//!    aggregate, stage-1 telemetry-only — see
//!    [`ab_store::AMBIENT_SURFACING_MODE`]) all get their telemetry consumed
//!    and reported — nothing re-aggregates forever as an invisible pending
//!    residue.
//!
//! Honest limits: `now` is the wall clock — a clock step larger than the
//! maturation window can consume rows early (misreading a future "used") or
//! sweep rows a running pass never aggregated; damage is bounded to one
//! step per key by the clamps. Long-run importance under this rule tracks
//! the duty cycle of use-days vs surfacing-days, not the used/surfaced
//! ratio; recalibrate with `retrieval_outcome_shadow` and steer the daemon
//! via the `AB_RETRIEVAL_OUTCOME_APPLY_*` env knobs.
//!
//! The daemon tick that runs this automatically is gated by
//! `AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY` (default OFF); the MCP tool
//! `retrieval_outcome_apply` defaults to a dry-run preview and writes only
//! with `confirm_apply=true`.

use ab_core::Result;
use ab_store::{MemoryRecord, RetrievalOutcomeShadowRow, StateStore};
use serde_json::{json, Value};
use std::sync::Arc;

/// Rows younger than this stay pending: every used_at attribution window
/// (memory_get 1800s, retrieval feedback
/// [`FEEDBACK_ATTRIBUTION_WINDOW_SECS`]) must have STRICTLY closed before a
/// surfacing may be read as "never used". The 3600s margin over the widest
/// window absorbs the boundary second and modest cross-process clock skew
/// (review finding, 2026-07-03).
pub const APPLY_MATURATION_SECS: i64 = 25_200;

/// How far back `memory_retrieval_feedback(outcome=used)` stamps `used_at`
/// on surfacings of the judged key. Wider than the memory_get window (1800s)
/// because explicit feedback often arrives at session end, hours after the
/// search that surfaced the memory. Must stay strictly below
/// [`APPLY_MATURATION_SECS`].
pub const FEEDBACK_ATTRIBUTION_WINDOW_SECS: i64 = 21_600;

/// The parameterized reinforce/decay rule, shared verbatim with the
/// `retrieval_outcome_shadow` what-if harness so preview and apply can never
/// disagree. Defaults are the op-class conservative point the shadow tool
/// documents (step 0.05, floor 0.1, ceiling 0.9).
#[derive(Debug, Clone, Copy)]
pub struct RuleParams {
    pub reinforce_step: f64,
    pub decay_step: f64,
    pub min_surfaced_for_decay: u64,
    pub floor: f64,
    pub ceiling: f64,
    /// When true (default), rows the store aggregate flags `protected`
    /// (kind=feedback, continuity must_block / constraint / warning) are
    /// exempt from the decay half: their consumption channel — ambient
    /// injection — never stamps `used_at`, so never-used telemetry on them
    /// is attribution bias, not deadness. Reinforce is unaffected. Kill
    /// switch: AB_RETRIEVAL_OUTCOME_APPLY_PROTECT_DISABLE=1.
    pub protect_classes: bool,
}

impl Default for RuleParams {
    fn default() -> Self {
        Self {
            reinforce_step: 0.05,
            decay_step: 0.05,
            min_surfaced_for_decay: 2,
            floor: 0.1,
            ceiling: 0.9,
            protect_classes: true,
        }
    }
}

impl RuleParams {
    /// Inverted (or NaN) bounds would make classify_rows dump EVERY key into
    /// the clamped buckets — which a confirmed pass then consumes without
    /// writing anything or leaving an audit trail. Refuse up front.
    pub fn validate(&self) -> std::result::Result<(), String> {
        if !(self.floor <= self.ceiling) {
            return Err(format!(
                "invalid rule params: floor ({}) must be <= ceiling ({})",
                self.floor, self.ceiling
            ));
        }
        Ok(())
    }
}

/// One concrete importance move the rule prescribes.
#[derive(Debug, Clone)]
pub struct RuleChange {
    pub key: String,
    pub surfaced_count: u64,
    pub used_count: u64,
    pub avg_rank: f64,
    pub importance: f64,
    pub would_be: f64,
    pub action: &'static str,
}

/// Full disposition of an aggregated telemetry slice under the rule.
///
/// Keys in `at_ceiling_keys` / `at_floor_keys` carry signal the rule cannot
/// act on (already clamped); `zero_step_keys` had an action prescribed but a
/// 0.0 step (that half of the rule disabled). An apply pass consumes both —
/// evidence the rule has fully observed must not re-aggregate forever.
/// `pending_below_min` keys are the opposite: real but insufficient
/// evidence, left unconsumed to accumulate.
#[derive(Debug, Default)]
pub struct Classified {
    pub changes: Vec<RuleChange>,
    pub at_ceiling_keys: Vec<String>,
    pub at_floor_keys: Vec<String>,
    pub zero_step_keys: Vec<String>,
    /// Constraint-class rows the decay half declined to touch (see
    /// `RuleParams::protect_classes`). Consumed by an apply pass like the
    /// clamped buckets — declined evidence must not re-aggregate forever.
    pub protected_decay_keys: Vec<String>,
    pub pending_below_min: u64,
}

/// Pure rule math — classes are disjoint by construction (used > 0 vs
/// used == 0). Monotone clamps: reinforce never LOWERS a row already above
/// the ceiling (skip), decay never RAISES one already at/below the floor
/// (skip) — mirroring the memory_decay_unused floor semantics.
pub fn classify_rows(rows: &[RetrievalOutcomeShadowRow], p: &RuleParams) -> Classified {
    let mut out = Classified::default();
    for r in rows {
        let (would_be, action) = if r.used_count > 0 {
            if r.importance >= p.ceiling {
                out.at_ceiling_keys.push(r.key.clone());
                continue;
            }
            (
                (r.importance + p.reinforce_step).min(p.ceiling),
                "reinforce",
            )
        } else if r.surfaced_count >= p.min_surfaced_for_decay {
            if p.protect_classes && r.protected {
                // Constraint-class row: never-used telemetry is attribution
                // bias (ambient consumption channel), so the rule declines
                // to decay. Bucketed, not dropped — the apply pass consumes
                // the evidence exactly like the clamped buckets.
                out.protected_decay_keys.push(r.key.clone());
                continue;
            }
            if r.importance <= p.floor {
                out.at_floor_keys.push(r.key.clone());
                continue;
            }
            ((r.importance - p.decay_step).max(p.floor), "decay")
        } else {
            // One-off (below-threshold) unused surfacing — no signal either
            // way YET. The apply pass leaves these rows unconsumed.
            out.pending_below_min += 1;
            continue;
        };
        if would_be == r.importance {
            // Zero-step (or float-degenerate) params: an action was
            // prescribed but moves nothing. Bucketed — not silently dropped —
            // so the apply pass still consumes the evidence (else a disabled
            // rule half re-aggregates the same keys forever; review finding,
            // 2026-07-03).
            out.zero_step_keys.push(r.key.clone());
            continue;
        }
        out.changes.push(RuleChange {
            key: r.key.clone(),
            surfaced_count: r.surfaced_count,
            used_count: r.used_count,
            avg_rank: r.avg_rank,
            importance: r.importance,
            would_be,
            action,
        });
    }
    out
}

/// Everything a confirmed (or previewed) pass did / would do.
#[derive(Debug)]
pub struct ApplyReport {
    pub dry_run: bool,
    pub rows_considered: usize,
    pub changes: Vec<RuleChange>,
    pub at_ceiling: u64,
    pub at_floor: u64,
    pub zero_step: u64,
    /// Constraint-class rows the decay half skipped under
    /// `RuleParams::protect_classes` (evidence still consumed).
    pub protected_skipped: u64,
    pub pending_below_min: u64,
    pub capped_out: u64,
    pub applied: u64,
    pub failed: u64,
    /// Keys whose evidence a concurrent pass consumed first — nothing was
    /// written for them here, and nothing needs to be.
    pub skipped_raced: u64,
    pub consumed_rows: u64,
    pub consumed_noaction_keys: u64,
    /// Pending mature rows of non-active memories swept this pass.
    pub orphans_consumed: u64,
    /// Pending mature ambient (bootstrap-mode) rows retired this pass —
    /// telemetry-only in stage 1, so retirement is their only consume path
    /// (it runs before the orphan sweep, so dead memories' ambient rows are
    /// counted here, not in orphans_consumed).
    pub ambient_retired: u64,
    pub audit_memory_key: Option<String>,
    pub net_importance_delta: f64,
}

/// One reinforce/decay pass over the unconsumed, mature telemetry slice.
///
/// `confirm=false` previews against the SAME slice the confirmed pass would
/// consume (unlike `retrieval_outcome_shadow`, which windows over the full
/// telemetry regardless of consumption). Nothing is written or consumed.
///
/// `max_changes` caps importance writes per pass; rows beyond the cap keep
/// their telemetry unconsumed and are reported in `capped_out` — a capped
/// pass defers, it never silently drops.
pub async fn run_apply_pass(
    store: &Arc<dyn StateStore>,
    params: &RuleParams,
    max_changes: usize,
    confirm: bool,
    now: i64,
) -> Result<ApplyReport> {
    if let Err(e) = params.validate() {
        return Err(ab_core::Error::Backend(e));
    }
    let cutoff = now - APPLY_MATURATION_SECS;
    let rows = store.retrieval_outcome_apply_rows(cutoff).await?;
    let rows_considered = rows.len();
    let classified = classify_rows(&rows, params);

    // Store order is deterministic (used DESC, surfaced DESC, key ASC), so
    // the cap always defers the same tail rather than a random subset.
    let mut changes = classified.changes;
    let capped_out = changes.len().saturating_sub(max_changes) as u64;
    changes.truncate(max_changes);

    if !confirm {
        return Ok(ApplyReport {
            dry_run: true,
            rows_considered,
            at_ceiling: classified.at_ceiling_keys.len() as u64,
            at_floor: classified.at_floor_keys.len() as u64,
            zero_step: classified.zero_step_keys.len() as u64,
            protected_skipped: classified.protected_decay_keys.len() as u64,
            pending_below_min: classified.pending_below_min,
            capped_out,
            applied: 0,
            failed: 0,
            skipped_raced: 0,
            consumed_rows: 0,
            consumed_noaction_keys: 0,
            orphans_consumed: 0,
            ambient_retired: 0,
            audit_memory_key: None,
            // Preview delta: what the writes below WOULD sum to.
            net_importance_delta: changes.iter().map(|c| c.would_be - c.importance).sum(),
            changes,
        });
    }

    // Rollback map FIRST: if the write loop dies mid-pass, the audit record
    // already carries every old value (outcome_valence_importance_apply
    // pattern). Sub-second nonce: two passes in the same unix second must not
    // collide — memory_save is an upsert and would silently replace the
    // previous pass's rollback map. The record is re-saved after the loop
    // with per-row outcomes (applied/failed/raced), so a rollback operator
    // replays only rows that actually landed.
    let audit_nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    let mut audit_memory_key: Option<String> = None;
    let save_audit = |outcomes: Option<&Vec<&'static str>>, changes: &[RuleChange]| {
        let audit_key = format!("retrieval_outcome_apply_{now}_{audit_nonce:09}");
        let audit_rows: Vec<Value> = changes
            .iter()
            .enumerate()
            .map(|(i, c)| {
                let mut row = json!({
                    "key": c.key,
                    "old_importance": c.importance,
                    "new_importance": c.would_be,
                    "action": c.action,
                    "surfaced_count": c.surfaced_count,
                    "used_count": c.used_count,
                });
                if let Some(outcomes) = outcomes {
                    row["outcome"] = json!(outcomes[i]);
                }
                row
            })
            .collect();
        let audit_body = json!({
            "schema": "agent_bridge.retrieval_outcome_apply_audit.v0",
            "applied_at": now,
            "params": {
                "reinforce_step": params.reinforce_step,
                "decay_step": params.decay_step,
                "min_surfaced_for_decay": params.min_surfaced_for_decay,
                "floor": params.floor,
                "ceiling": params.ceiling,
            },
            "rollback": "for each row with outcome=applied (or no outcome field — the \
                pass died before amending): memory_set_importance(key, old_importance); \
                consumed telemetry rows stay consumed (they were still observed)",
            "rows": audit_rows,
        });
        MemoryRecord {
            key: audit_key,
            kind: "observation".to_string(),
            content: format!(
                "retrieval_outcome_apply rollback map ({} rows)\n```json\n{}\n```",
                changes.len(),
                serde_json::to_string_pretty(&audit_body)
                    .unwrap_or_else(|_| audit_body.to_string())
            ),
            tags: vec![
                "retrieval_outcome".to_string(),
                "importance_apply".to_string(),
                "audit".to_string(),
                "rollback_map".to_string(),
                // Rollback maps are operator plumbing with a bounded useful life
                // (the rollback window). Past it they are near-token-identical
                // boilerplate that floods top-k on valence/retrieval queries
                // (write-side consolidation audit, 2026-07-11). The `ttl:Nd` tag
                // makes `record_ttl_is_live` suppress them from retrieval once
                // the window passes; memory_compact then retires them.
                "ttl:14d".to_string(),
            ],
            related_keys: Vec::new(),
            // DISTINCT per-pass scope: successive audit maps are near
            // token-identical boilerplate, so a shared NULL scope would let
            // the same-kind+same-scope contradiction detector supersede every
            // previous rollback map (the valence-audit lesson, 2026-07-02).
            scope: Some(format!("retrieval-outcome-audit:{now}_{audit_nonce:09}")),
            created_at: now,
            updated_at: now,
            last_accessed_at: now,
            access_count: 0,
            // Deliberately LOW: with the daemon gate on, one of these lands
            // per acting day — they are operator plumbing, not recall
            // material, and must not crowd search pages (review finding,
            // 2026-07-03).
            importance: 0.2,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    };
    if !changes.is_empty() {
        let rec = save_audit(None, &changes);
        let key = rec.key.clone();
        if let Err(e) = store.memory_save(&rec).await {
            return Err(ab_core::Error::Backend(format!(
                "refusing to apply without a persisted rollback map: memory_save failed: {e}"
            )));
        }
        audit_memory_key = Some(key);
    }

    // Consume-and-write per key in ONE store transaction, consume first: a
    // concurrent pass (daemon tick vs manual tool, cross-process) that
    // aggregated the same slice consumes 0 rows here and writes nothing —
    // one batch of evidence, at most one step.
    let (mut applied, mut failed, mut skipped_raced) = (0u64, 0u64, 0u64);
    let (mut consumed_rows, mut consumed_noaction_keys) = (0u64, 0u64);
    let mut net_delta = 0.0f64;
    let mut outcomes: Vec<&'static str> = Vec::with_capacity(changes.len());
    for c in &changes {
        match store
            .consume_and_apply_importance(&c.key, c.would_be, cutoff)
            .await
        {
            Ok((0, _)) => {
                // A concurrent pass consumed this key's evidence first.
                skipped_raced += 1;
                outcomes.push("raced");
            }
            Ok((n, true)) => {
                applied += 1;
                consumed_rows += n;
                net_delta += c.would_be - c.importance;
                outcomes.push("applied");
            }
            Ok((n, false)) => {
                // Evidence consumed but the memory vanished between aggregate
                // and write — nothing to move, and the telemetry is correctly
                // retired with it.
                failed += 1;
                consumed_rows += n;
                outcomes.push("failed");
            }
            Err(e) => {
                // Transaction rolled back: nothing consumed, nothing written;
                // the key simply retries next pass.
                tracing::warn!(key = %c.key, error = %e,
                    "retrieval_outcome_apply: consume+write transaction failed");
                failed += 1;
                outcomes.push("failed");
            }
        }
    }

    // Amend the audit map with what actually happened. Best-effort: the
    // intent map is already durable, and a missing amendment reads as
    // "pass died before amending" per the rollback instructions.
    if let Some(_key) = &audit_memory_key {
        let rec = save_audit(Some(&outcomes), &changes);
        if let Err(e) = store.memory_save(&rec).await {
            tracing::warn!(error = %e,
                "retrieval_outcome_apply: audit outcome amendment failed (intent map remains)");
        }
    }

    // Clamped, zero-step, and protected keys: the rule cannot (or will not)
    // act on them, but their rows are real observed signal — consume so they
    // don't pile up as a permanently re-aggregated dead slice.
    for key in classified
        .at_ceiling_keys
        .iter()
        .chain(classified.at_floor_keys.iter())
        .chain(classified.zero_step_keys.iter())
        .chain(classified.protected_decay_keys.iter())
    {
        match store.consume_retrieval_surfacings(key, cutoff).await {
            Ok(n) => {
                consumed_rows += n;
                consumed_noaction_keys += 1;
            }
            Err(e) => {
                tracing::warn!(key = %key, error = %e,
                    "retrieval_outcome_apply: consume failed for clamped/zero-step key");
            }
        }
    }

    // Ambient retirement FIRST: bootstrap-mode rows are mode-excluded from
    // the aggregate (stage-1 telemetry-only), so no per-key consume ever
    // reaches them. Retire the mature slice here or it squats the pending
    // pool. Running before the orphan sweep keeps the two counters exact:
    // this sweep has no status filter, so ambient rows of dead memories are
    // billed to ambient_retired, and orphans_consumed counts only real
    // (non-ambient) evidence of dead memories (review finding, 2026-07-05).
    // Fail-soft: a failed retirement only delays, never corrupts.
    let ambient_retired = match store.consume_ambient_surfacings(cutoff).await {
        Ok(n) => n,
        Err(e) => {
            tracing::warn!(error = %e, "retrieval_outcome_apply: ambient retirement failed");
            0
        }
    };

    // Orphan sweep: pending mature rows whose memory is no longer active are
    // invisible to the aggregate's status='active' JOIN — retire them so the
    // pending slice stays a truthful work queue (and a later re-creation of
    // the same key doesn't inherit stale never-used evidence).
    let orphans_consumed = match store.consume_orphaned_surfacings(cutoff).await {
        Ok(n) => n,
        Err(e) => {
            tracing::warn!(error = %e, "retrieval_outcome_apply: orphan sweep failed");
            0
        }
    };

    Ok(ApplyReport {
        dry_run: false,
        rows_considered,
        at_ceiling: classified.at_ceiling_keys.len() as u64,
        at_floor: classified.at_floor_keys.len() as u64,
        zero_step: classified.zero_step_keys.len() as u64,
        protected_skipped: classified.protected_decay_keys.len() as u64,
        pending_below_min: classified.pending_below_min,
        capped_out,
        applied,
        failed,
        skipped_raced,
        consumed_rows,
        consumed_noaction_keys,
        orphans_consumed,
        ambient_retired,
        audit_memory_key,
        // Applied delta: what the successful writes actually summed to
        // (intentionally ≠ the preview definition when writes fail or race).
        net_importance_delta: net_delta,
        changes,
    })
}

/// Gate for the daemon tick that runs a confirmed pass automatically.
/// Default OFF — flipping it on is a per-deployment machine.env decision.
pub fn apply_tick_enabled() -> bool {
    apply_tick_enabled_from(
        std::env::var("AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY")
            .ok()
            .as_deref(),
    )
}

fn apply_tick_enabled_from(v: Option<&str>) -> bool {
    v.map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

/// Tick cadence. The daily default IS the pacing knob: with consumption,
/// each key moves at most one step per pass, so "daily tick" means at most
/// ±0.05/day per memory — the memory_decay_unused op-class rate.
pub fn apply_tick_secs() -> u64 {
    apply_tick_secs_from(
        std::env::var("AB_RETRIEVAL_OUTCOME_APPLY_TICK_SECS")
            .ok()
            .as_deref(),
    )
}

fn apply_tick_secs_from(v: Option<&str>) -> u64 {
    v.and_then(|s| s.parse().ok())
        .unwrap_or(86_400)
        .clamp(3_600, 7 * 86_400)
}

/// Constraint-class decay protection, default ON.
/// AB_RETRIEVAL_OUTCOME_APPLY_PROTECT_DISABLE=1 (or true) turns it off —
/// same knob family as the other apply-rule overrides, so recalibration is
/// a machine.env edit, not a redeploy.
pub fn protect_classes_enabled() -> bool {
    protect_classes_enabled_from(
        std::env::var("AB_RETRIEVAL_OUTCOME_APPLY_PROTECT_DISABLE")
            .ok()
            .as_deref(),
    )
}

fn protect_classes_enabled_from(v: Option<&str>) -> bool {
    !v.map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

/// Rule params for the daemon tick, steerable per-deployment via machine.env —
/// the shadow tool's calibration story ("tune params = re-run the read-only
/// tool") needs an actuator that can be re-pointed without a redeploy
/// (review finding, 2026-07-03). Invalid combinations (floor > ceiling, NaN)
/// fall back to the defaults with a warning rather than silently consuming
/// evidence.
pub fn tick_rule_params() -> RuleParams {
    let read = |name: &str| std::env::var(name).ok();
    let params = tick_rule_params_from(
        read("AB_RETRIEVAL_OUTCOME_APPLY_REINFORCE_STEP").as_deref(),
        read("AB_RETRIEVAL_OUTCOME_APPLY_DECAY_STEP").as_deref(),
        read("AB_RETRIEVAL_OUTCOME_APPLY_MIN_SURFACED").as_deref(),
        read("AB_RETRIEVAL_OUTCOME_APPLY_FLOOR").as_deref(),
        read("AB_RETRIEVAL_OUTCOME_APPLY_CEILING").as_deref(),
        read("AB_RETRIEVAL_OUTCOME_APPLY_PROTECT_DISABLE").as_deref(),
    );
    if params.validate().is_err() {
        tracing::warn!(
            "retrieval-outcome-apply: invalid AB_RETRIEVAL_OUTCOME_APPLY_* rule params \
             (floor > ceiling); falling back to defaults"
        );
        return RuleParams::default();
    }
    params
}

fn tick_rule_params_from(
    reinforce: Option<&str>,
    decay: Option<&str>,
    min_surfaced: Option<&str>,
    floor: Option<&str>,
    ceiling: Option<&str>,
    protect_disable: Option<&str>,
) -> RuleParams {
    let d = RuleParams::default();
    let f = |v: Option<&str>, default: f64| {
        v.and_then(|s| s.parse::<f64>().ok())
            .map(|x| x.clamp(0.0, 1.0))
            .unwrap_or(default)
    };
    RuleParams {
        reinforce_step: f(reinforce, d.reinforce_step),
        decay_step: f(decay, d.decay_step),
        min_surfaced_for_decay: min_surfaced
            .and_then(|s| s.parse::<u64>().ok())
            .map(|x| x.max(1))
            .unwrap_or(d.min_surfaced_for_decay),
        floor: f(floor, d.floor),
        ceiling: f(ceiling, d.ceiling),
        protect_classes: protect_classes_enabled_from(protect_disable),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(key: &str, surfaced: u64, used: u64, importance: f64) -> RetrievalOutcomeShadowRow {
        RetrievalOutcomeShadowRow {
            key: key.to_string(),
            surfaced_count: surfaced,
            used_count: used,
            avg_rank: 1.0,
            last_surfaced_at: 0,
            importance,
            protected: false,
        }
    }

    fn prow(key: &str, surfaced: u64, used: u64, importance: f64) -> RetrievalOutcomeShadowRow {
        RetrievalOutcomeShadowRow {
            protected: true,
            ..row(key, surfaced, used, importance)
        }
    }

    #[test]
    fn classify_protected_rows_skip_decay_but_still_reinforce() {
        let rows = vec![
            prow("prot_unused", 5, 0, 0.9), // decay half declines — bucketed
            prow("prot_used", 2, 1, 0.5),   // reinforce unaffected
            row("plain_unused", 5, 0, 0.9), // decays normally
        ];
        let c = classify_rows(&rows, &RuleParams::default());
        assert_eq!(c.protected_decay_keys, vec!["prot_unused".to_string()]);
        let keys: Vec<&str> = c.changes.iter().map(|ch| ch.key.as_str()).collect();
        assert_eq!(keys, vec!["prot_used", "plain_unused"]);
        assert_eq!(c.changes[0].action, "reinforce");
        assert_eq!(c.changes[1].action, "decay");

        // Kill switch: with protection off the same slice decays normally.
        let off = RuleParams {
            protect_classes: false,
            ..RuleParams::default()
        };
        let c2 = classify_rows(&rows, &off);
        assert!(c2.protected_decay_keys.is_empty());
        assert_eq!(c2.changes.len(), 3);
    }

    #[test]
    fn protect_env_parsing_default_on() {
        assert!(protect_classes_enabled_from(None));
        assert!(protect_classes_enabled_from(Some("0")));
        assert!(protect_classes_enabled_from(Some("garbage")));
        assert!(!protect_classes_enabled_from(Some("1")));
        assert!(!protect_classes_enabled_from(Some("TRUE")));
    }

    #[test]
    fn classify_disjoint_actions_and_clamps() {
        let rows = vec![
            row("used_mid", 3, 1, 0.5),        // reinforce 0.5 → 0.55
            row("used_at_ceiling", 2, 2, 0.9), // skip, at ceiling
            row("unused_hot", 4, 0, 0.8),      // decay 0.8 → 0.75
            row("unused_at_floor", 5, 0, 0.1), // skip, at floor
            row("unused_single", 1, 0, 0.7),   // pending below min
        ];
        let c = classify_rows(&rows, &RuleParams::default());
        assert_eq!(c.changes.len(), 2);
        assert_eq!(c.changes[0].key, "used_mid");
        assert!((c.changes[0].would_be - 0.55).abs() < 1e-9);
        assert_eq!(c.changes[0].action, "reinforce");
        assert_eq!(c.changes[1].key, "unused_hot");
        assert!((c.changes[1].would_be - 0.75).abs() < 1e-9);
        assert_eq!(c.changes[1].action, "decay");
        assert_eq!(c.at_ceiling_keys, vec!["used_at_ceiling".to_string()]);
        assert_eq!(c.at_floor_keys, vec!["unused_at_floor".to_string()]);
        assert!(c.zero_step_keys.is_empty());
        assert_eq!(c.pending_below_min, 1);
    }

    #[test]
    fn classify_caps_at_bounds_never_crosses() {
        let rows = vec![
            row("near_ceiling", 1, 1, 0.88), // 0.88 + 0.05 caps at 0.9
            row("near_floor", 3, 0, 0.12),   // 0.12 - 0.05 caps at 0.1
        ];
        let c = classify_rows(&rows, &RuleParams::default());
        assert!((c.changes[0].would_be - 0.9).abs() < 1e-9);
        assert!((c.changes[1].would_be - 0.1).abs() < 1e-9);
    }

    #[test]
    fn classify_zero_steps_bucket_for_consumption() {
        // A disabled rule half must not leave its keys in limbo: they land in
        // zero_step_keys so the apply pass consumes their evidence instead of
        // re-aggregating it forever (review finding, 2026-07-03).
        let rows = vec![row("a", 3, 1, 0.5), row("b", 3, 0, 0.5)];
        let p = RuleParams {
            reinforce_step: 0.0,
            decay_step: 0.0,
            ..RuleParams::default()
        };
        let c = classify_rows(&rows, &p);
        assert!(c.changes.is_empty());
        assert!(c.at_ceiling_keys.is_empty() && c.at_floor_keys.is_empty());
        assert_eq!(
            c.zero_step_keys,
            vec!["a".to_string(), "b".to_string()],
            "zero-step rows are bucketed, not dropped"
        );
        assert_eq!(c.pending_below_min, 0);
    }

    #[test]
    fn feedback_window_strictly_inside_maturation() {
        // Invariant 3: a row must not be consumable while an attribution
        // window could still stamp it — STRICT, so the boundary second (plus
        // modest clock skew) is on the safe side.
        assert!(FEEDBACK_ATTRIBUTION_WINDOW_SECS < APPLY_MATURATION_SECS);
        assert!(
            APPLY_MATURATION_SECS - FEEDBACK_ATTRIBUTION_WINDOW_SECS >= 3_600,
            "keep a real margin, not just one tick"
        );
    }

    #[test]
    fn rule_params_validate_rejects_inverted_bounds() {
        let bad = RuleParams {
            floor: 0.8,
            ceiling: 0.2,
            ..RuleParams::default()
        };
        assert!(bad.validate().is_err());
        let nan = RuleParams {
            floor: f64::NAN,
            ..RuleParams::default()
        };
        assert!(nan.validate().is_err(), "NaN bounds must not pass");
        assert!(RuleParams::default().validate().is_ok());
    }

    #[test]
    fn tick_env_parsing_defaults_and_clamps() {
        assert!(!apply_tick_enabled_from(None));
        assert!(!apply_tick_enabled_from(Some("0")));
        assert!(apply_tick_enabled_from(Some("1")));
        assert!(apply_tick_enabled_from(Some("TRUE")));
        assert_eq!(apply_tick_secs_from(None), 86_400);
        assert_eq!(apply_tick_secs_from(Some("60")), 3_600); // clamp low
        assert_eq!(apply_tick_secs_from(Some("9999999")), 7 * 86_400); // clamp high
        assert_eq!(apply_tick_secs_from(Some("garbage")), 86_400);
    }

    #[test]
    fn tick_rule_params_env_overrides_and_defaults() {
        let d = tick_rule_params_from(None, None, None, None, None, None);
        assert!((d.reinforce_step - 0.05).abs() < 1e-9);
        assert_eq!(d.min_surfaced_for_decay, 2);
        assert!(d.protect_classes, "protection defaults ON");
        let t = tick_rule_params_from(
            Some("0.02"),
            Some("0.01"),
            Some("4"),
            Some("0.2"),
            Some("0.8"),
            Some("1"),
        );
        assert!((t.reinforce_step - 0.02).abs() < 1e-9);
        assert!((t.decay_step - 0.01).abs() < 1e-9);
        assert_eq!(t.min_surfaced_for_decay, 4);
        assert!((t.floor - 0.2).abs() < 1e-9 && (t.ceiling - 0.8).abs() < 1e-9);
        assert!(!t.protect_classes, "PROTECT_DISABLE=1 turns protection off");
        // Garbage falls back per-field; out-of-range clamps; min>=1.
        let g = tick_rule_params_from(Some("abc"), Some("7.0"), Some("0"), None, None, None);
        assert!((g.reinforce_step - 0.05).abs() < 1e-9);
        assert!((g.decay_step - 1.0).abs() < 1e-9);
        assert_eq!(g.min_surfaced_for_decay, 1);
    }
}
