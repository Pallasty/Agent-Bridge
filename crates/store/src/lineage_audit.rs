//! Lineage / provenance audit predicates — read-only anomaly scan over the
//! semantic-event spine (borrow T7/P5).
//!
//! ## Problem
//! AB emits an append-only `semantic_events` ledger (the SSB typed event spine:
//! `actor, source, action, target, verdict_status, evidence, facts`) but has no
//! *post-hoc anomaly scanner* over it. The continuity / Goal-C lane wants a
//! read-only "honest ledger" view — *which actors are failing verification in
//! bursts, which effects are recorded without traceable proof* — without adding
//! yet another gate.
//!
//! ## Borrow
//! `nexus-civilization/server/core/governance/compliance.py::ComplianceMonitor`
//! is a rule-based, **read-only** scanner: it reads an event ledger + a causal
//! DAG and records flags to a governance log — it never mutates world state
//! ("从 GovernanceAgent 的视角，ComplianceMonitor 是法制院"). We port three of
//! its five checks, faithfully adapted to AB's event spine:
//!
//! - `_check_severity_burst` → [`severity_burst`] (rapid adverse-verdict run).
//! - `_check_cascade_depth` → [`cascade_depth`] (deep lineage chain).
//! - `_check_resource_leak` → [`conservation_leak`] (un-provenanced effect or
//!   dangling lineage reference — "any delta with no lineage-traceable admitted
//!   entry ⇒ un-provenanced mutation").
//!
//! The two AB-irrelevant checks (`_check_constitutional` world-state physics,
//! `RateAbuseDetection` per-tick command rate) are intentionally **not** ported.
//!
//! ## Honest substrate note (2026-06-28)
//! This is the *analyzer*, not the data. On the surveyed node the spine is still
//! sparse (`semantic_events` carries a handful of `session/bootstrap` rows and
//! no lineage links in `facts`), so a live run today reports ~0 findings — the
//! value is (a) the unit-tested predicate library, ready as producers fill the
//! spine, and (b) the honest read-only report shape. The eval prints the
//! substrate size so a sparse run is never mistaken for a clean one. The
//! predicates are *not* true-by-construction: the tests below fire them on
//! synthetic adverse data.
//!
//! ## Discipline (mirrors [`crate::quant`] / [`crate::coactivation_latch`] /
//! [`crate::connectivity_repair`])
//! - **Read-only / report-only.** Computes findings; writes nothing, opens no
//!   DB, calls no MCP. This is a continuity *report*, **not** a gate chain
//!   (the Goal-C RSI doc: "a continuity honest ledger, NOT another gate chain").
//! - **Deterministic.** No RNG, no clock, no `HashMap` iteration — `BTree*`
//!   throughout, every tie broken by id; the input is processed through a
//!   total-canonical-order working copy so the report is identical regardless of
//!   row order (even on a degenerate duplicate id).
//! - **DB-agnostic core.** Operates on plain [`AuditEvent`] values; the
//!   read-only SQLite projection lives in `examples/lineage_audit_eval.rs`.

use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;

/// Adverse-ness of an event, ordered `Benign < Watch < Adverse`. An adapter
/// maps its native signal (verdict_status, notification severity, …) into this.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// Healthy / expected (e.g. `verdict_status = "verified"`).
    Benign,
    /// Uncertain / soft-negative (e.g. `verdict_status = "unknown"`).
    Watch,
    /// Failed / hard-negative (e.g. `verdict_status = "not_verified"`, an error).
    Adverse,
}

/// Whether an event's effect is traceable to an admitted/verified lineage entry.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Provenance {
    /// Effect is backed by a traceable admitted/verified entry (or is a benign,
    /// non-effecting observation).
    Admitted,
    /// An effect with no lineage-traceable admitted entry — un-provenanced.
    Unprovenanced,
}

/// One normalized provenance/lineage event for audit — a projection of a
/// `semantic_events` row (or any append-only ledger row).
#[derive(Debug, Clone, PartialEq)]
pub struct AuditEvent {
    /// Monotonic, unique event id (ordering key + lineage-edge target).
    pub id: i64,
    /// Event time (unix seconds) — the burst-window axis.
    pub ts: i64,
    /// Grouping key for burst detection (e.g. actor, source, `source/action`).
    pub group: String,
    /// Adverse-ness classification (adapter-mapped).
    pub severity: Severity,
    /// Provenance classification (adapter-mapped) for the conservation-leak check.
    pub provenance: Provenance,
    /// Lineage/causal parent event ids (empty when the ledger carries no link).
    pub parents: Vec<i64>,
    /// Short human label (e.g. `source/action`) carried into findings. Logic-free.
    pub label: String,
}

/// Tuning for [`audit`]. Defaults track nexus `ComplianceMonitor` thresholds:
/// its 5-tick burst window becomes 300s and the counts are carried over; the
/// cascade limit is node-counted (one node stricter than nexus — see
/// [`cascade_depth`]), not edge-counted.
#[derive(Debug, Clone)]
pub struct AuditConfig {
    /// Sliding window (seconds) for the severity-burst check.
    pub burst_window_secs: i64,
    /// `>=` this many at/above [`AuditConfig::burst_floor`] inside one window,
    /// per group → flag (nexus `SEVERITY_BURST_COUNT` = 4).
    pub burst_min_count: usize,
    /// Count only events whose severity is `>=` this floor.
    pub burst_floor: Severity,
    /// Lineage chain depth (in nodes; a root = depth 1) `>=` this → flag
    /// (nexus `CASCADE_DEPTH_LIMIT` = 6).
    pub cascade_depth_limit: usize,
    /// Cap on findings per kind (`0` = unlimited). Findings are ordered
    /// deterministically before the cap (by salience for bursts/cascades —
    /// count/depth desc; by id for leaks), so the cap is stable and reproducible.
    pub max_findings_per_kind: usize,
}

impl Default for AuditConfig {
    fn default() -> Self {
        Self {
            burst_window_secs: 300,
            burst_min_count: 4,
            burst_floor: Severity::Adverse,
            cascade_depth_limit: 6,
            max_findings_per_kind: 0,
        }
    }
}

/// A severity-burst finding: a group with `count` at/above-floor events inside
/// one `burst_window_secs` window (the densest such window for that group).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BurstFinding {
    pub group: String,
    pub count: usize,
    pub window_start_ts: i64,
    pub window_end_ts: i64,
    /// Ids of the events in the flagged window, ascending.
    pub event_ids: Vec<i64>,
    pub reason: String,
}

/// A cascade-depth finding: an event whose lineage chain is unexpectedly deep.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CascadeFinding {
    pub event_id: i64,
    /// Longest ancestor chain length in nodes (the event itself = 1).
    pub depth: usize,
    /// Up to 5 root ancestor ids (no present parents), ascending.
    pub root_ids: Vec<i64>,
    pub label: String,
    pub reason: String,
}

/// What kind of provenance gap a [`LeakFinding`] records.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LeakKind {
    /// An effect with no lineage-traceable admitted entry.
    Unprovenanced,
    /// References a parent id absent from the scanned event set.
    DanglingParent,
}

/// A conservation-leak finding: an un-provenanced effect or a dangling parent
/// reference (the AB analog of nexus's unexplained-resource-growth check).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LeakFinding {
    pub event_id: i64,
    pub kind: LeakKind,
    pub label: String,
    /// Parent ids that resolve to no scanned event (only for `DanglingParent`).
    pub dangling_parents: Vec<i64>,
    pub reason: String,
}

/// Read-only audit report — the full set of findings plus scan totals. Mirrors
/// nexus `ComplianceReport` (events_scanned + the flag lists).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LineageAuditReport {
    pub events_scanned: usize,
    /// Events at severity [`Severity::Adverse`].
    pub adverse_events: usize,
    /// Distinct grouping keys present.
    pub groups: usize,
    pub bursts: Vec<BurstFinding>,
    pub cascades: Vec<CascadeFinding>,
    pub leaks: Vec<LeakFinding>,
}

/// Run all three audit checks over `events` and collect findings into a report.
/// Read-only: returns findings, writes nothing. Order-independent — the input is
/// processed through a working copy sorted by a *total* canonical order, so the
/// report is identical regardless of row order even if two rows share an id
/// (ids are a PK and unique in practice; the canonical sort makes the degenerate
/// duplicate case deterministic rather than input-order dependent).
pub fn audit(events: &[AuditEvent], cfg: &AuditConfig) -> LineageAuditReport {
    let mut sorted: Vec<&AuditEvent> = events.iter().collect();
    sorted.sort_by(|a, b| canon_cmp(a, b));

    let groups: BTreeSet<&str> = sorted.iter().map(|e| e.group.as_str()).collect();
    let adverse_events = sorted
        .iter()
        .filter(|e| e.severity == Severity::Adverse)
        .count();

    LineageAuditReport {
        events_scanned: sorted.len(),
        adverse_events,
        groups: groups.len(),
        bursts: severity_burst(&sorted, cfg),
        cascades: cascade_depth(&sorted, cfg),
        leaks: conservation_leak(&sorted, cfg),
    }
}

/// **Severity-burst** — flag any group with `>= cfg.burst_min_count` events at
/// or above `cfg.burst_floor` inside any `cfg.burst_window_secs` window. Reports
/// the densest qualifying window per group (earliest on a tie). Borrow of
/// `_check_severity_burst`.
///
/// Reframe vs nexus: nexus counts over a *fixed* `[tick-W, tick]` lookback and
/// fans one event across every `affected_city` it touches; we compute the
/// *densest sliding* window per single [`AuditEvent::group`] (one event = one
/// group, no fan-out). Same count threshold, finer-grained window.
pub fn severity_burst(sorted: &[&AuditEvent], cfg: &AuditConfig) -> Vec<BurstFinding> {
    // Group → ts-sorted at/above-floor events.
    let mut by_group: BTreeMap<&str, Vec<&AuditEvent>> = BTreeMap::new();
    for e in sorted {
        if e.severity >= cfg.burst_floor {
            by_group.entry(e.group.as_str()).or_default().push(e);
        }
    }

    let mut findings = Vec::new();
    for (group, evs) in &by_group {
        // `evs` is already id-sorted (it inherits `sorted`'s order); make the
        // window axis explicit by sorting on (ts, id).
        let mut evs = evs.clone();
        evs.sort_by(|a, b| a.ts.cmp(&b.ts).then(a.id.cmp(&b.id)));

        // Two-pointer densest window: for each right edge, shrink from the left
        // until the span fits `burst_window_secs`; track the strictly-densest
        // (so ties keep the earliest window).
        let mut left = 0usize;
        let mut best_count = 0usize;
        let mut best_range = (0usize, 0usize);
        for right in 0..evs.len() {
            while evs[right].ts - evs[left].ts > cfg.burst_window_secs {
                left += 1;
            }
            let count = right - left + 1;
            if count > best_count {
                best_count = count;
                best_range = (left, right);
            }
        }

        if best_count >= cfg.burst_min_count {
            let window = &evs[best_range.0..=best_range.1];
            let mut event_ids: Vec<i64> = window.iter().map(|e| e.id).collect();
            event_ids.sort_unstable();
            findings.push(BurstFinding {
                group: (*group).to_string(),
                count: best_count,
                window_start_ts: window.first().map(|e| e.ts).unwrap_or(0),
                window_end_ts: window.last().map(|e| e.ts).unwrap_or(0),
                event_ids,
                reason: format!(
                    "group '{group}': {best_count} events >= {:?} within {}s — rapid escalation",
                    cfg.burst_floor, cfg.burst_window_secs
                ),
            });
        }
    }

    // Deterministic order: most-events-first, then group name.
    findings.sort_by(|a, b| b.count.cmp(&a.count).then(a.group.cmp(&b.group)));
    cap(findings, cfg.max_findings_per_kind)
}

/// **Cascade-depth** — flag events whose longest ancestor chain (over present
/// parent edges) reaches `cfg.cascade_depth_limit`. Borrow of
/// `_check_cascade_depth` (nexus reads a rustworkx DAG; we read the
/// [`AuditEvent::parents`] edges, following only parents present in the set so
/// phantom depth is never counted — a dangling parent is a *leak*, not depth).
///
/// Depth is counted in **nodes** (a parentless root = depth 1), so the threshold
/// fires one node *earlier* than nexus's edge-counted `chain_depth` (root = 0) —
/// intentional and slightly stricter, *not* "identical". Computed iteratively
/// (a Kahn-style longest-path DP — no recursion, so no stack overflow on long
/// chains). A cycle is itself anomalous and has no well-defined finite ancestry,
/// so its members are resolved deterministically from their acyclic in-edges
/// only; every genuine DAG node still gets its exact longest depth regardless of
/// any cycle elsewhere (so a real deep chain is never missed).
pub fn cascade_depth(sorted: &[&AuditEvent], cfg: &AuditConfig) -> Vec<CascadeFinding> {
    let present: BTreeSet<i64> = sorted.iter().map(|e| e.id).collect();
    // id → present parent ids (deduped, self-loops dropped). `sorted` is in
    // canonical order, so last-write-wins per id is deterministic on duplicates.
    let mut parents: BTreeMap<i64, Vec<i64>> = BTreeMap::new();
    let mut label: BTreeMap<i64, &str> = BTreeMap::new();
    for e in sorted {
        let ps: BTreeSet<i64> = e
            .parents
            .iter()
            .copied()
            .filter(|p| *p != e.id && present.contains(p))
            .collect();
        parents.insert(e.id, ps.into_iter().collect());
        label.insert(e.id, e.label.as_str());
    }

    let depth = compute_depths(&parents);
    let mut findings = Vec::new();
    // Iterate the depth map (one entry per id, ascending) → one finding per id.
    for (&id, &d) in &depth {
        if d >= cfg.cascade_depth_limit {
            let roots = root_ids(id, &parents, 5);
            findings.push(CascadeFinding {
                event_id: id,
                depth: d,
                root_ids: roots.clone(),
                label: label.get(&id).copied().unwrap_or("").to_string(),
                reason: format!(
                    "event {id} has lineage depth {d} (limit {}); roots {roots:?}",
                    cfg.cascade_depth_limit
                ),
            });
        }
    }

    // Deepest-first, then by id.
    findings.sort_by(|a, b| b.depth.cmp(&a.depth).then(a.event_id.cmp(&b.event_id)));
    cap(findings, cfg.max_findings_per_kind)
}

/// **Conservation-leak** — flag (a) un-provenanced effects and (b) dangling
/// lineage references. Borrow of `_check_resource_leak`, reframed per the RSI
/// backlog: "any delta with no lineage-traceable admitted entry ⇒ un-provenanced
/// mutation".
pub fn conservation_leak(sorted: &[&AuditEvent], cfg: &AuditConfig) -> Vec<LeakFinding> {
    let present: BTreeSet<i64> = sorted.iter().map(|e| e.id).collect();
    let mut findings = Vec::new();
    for e in sorted {
        if e.provenance == Provenance::Unprovenanced {
            findings.push(LeakFinding {
                event_id: e.id,
                kind: LeakKind::Unprovenanced,
                label: e.label.clone(),
                dangling_parents: Vec::new(),
                reason: format!(
                    "event {} records an effect with no traceable admitted entry",
                    e.id
                ),
            });
        }
        // Parents that resolve to no scanned event (self-id already excluded).
        let dangling: Vec<i64> = e
            .parents
            .iter()
            .copied()
            .filter(|p| *p != e.id && !present.contains(p))
            .collect::<BTreeSet<i64>>()
            .into_iter()
            .collect();
        if !dangling.is_empty() {
            findings.push(LeakFinding {
                event_id: e.id,
                kind: LeakKind::DanglingParent,
                label: e.label.clone(),
                reason: format!(
                    "event {} references absent lineage parent(s) {:?}",
                    e.id, dangling
                ),
                dangling_parents: dangling,
            });
        }
    }

    // Deterministic: by event id, then kind (Unprovenanced before DanglingParent
    // via declaration order).
    findings.sort_by(|a, b| {
        a.event_id
            .cmp(&b.event_id)
            .then((a.kind as u8).cmp(&(b.kind as u8)))
    });
    cap(findings, cfg.max_findings_per_kind)
}

/// A total order over events, so the working copy in [`audit`] sorts
/// identically for any input row order — even when two rows share an id.
fn canon_cmp(a: &AuditEvent, b: &AuditEvent) -> std::cmp::Ordering {
    a.id.cmp(&b.id)
        .then(a.ts.cmp(&b.ts))
        .then_with(|| a.group.cmp(&b.group))
        .then(a.severity.cmp(&b.severity))
        .then(a.provenance.cmp(&b.provenance))
        .then_with(|| a.parents.cmp(&b.parents))
        .then_with(|| a.label.cmp(&b.label))
}

/// Longest ancestor-chain length per id, in **nodes** (a parentless root = 1),
/// computed iteratively so a long chain can never overflow the native stack.
///
/// A Kahn-style longest-path DP over the child→parent DAG: a node is resolved
/// once all its parents are, with `depth = 1 + max(parent depths)`. Nodes left
/// unresolved are in (or downstream of) a cycle — itself anomalous — and are
/// then resolved in a single ascending-id pass from their already-resolved
/// (acyclic) in-edges only: deterministic, bounded, and non-divergent, while
/// every genuine DAG node keeps its exact longest depth.
fn compute_depths(parents: &BTreeMap<i64, Vec<i64>>) -> BTreeMap<i64, usize> {
    // children[p] = nodes that list p as a parent; pending[c] = unresolved parents.
    let mut children: BTreeMap<i64, Vec<i64>> = BTreeMap::new();
    let mut pending: BTreeMap<i64, usize> = BTreeMap::new();
    for (&id, ps) in parents {
        pending.insert(id, ps.len());
        for &p in ps {
            children.entry(p).or_default().push(id);
        }
    }

    let resolve = |id: i64, depth: &BTreeMap<i64, usize>| -> usize {
        parents
            .get(&id)
            .into_iter()
            .flatten()
            .filter_map(|p| depth.get(p).copied())
            .max()
            .map(|m| m + 1)
            .unwrap_or(1)
    };

    let mut depth: BTreeMap<i64, usize> = BTreeMap::new();
    // Ready = nodes with all parents resolved; seed with roots (0 parents).
    // BTreeSet → ascending-id processing keeps everything deterministic.
    let mut ready: BTreeSet<i64> = pending
        .iter()
        .filter(|(_, &c)| c == 0)
        .map(|(&id, _)| id)
        .collect();
    while let Some(&id) = ready.iter().next() {
        ready.remove(&id);
        depth.insert(id, resolve(id, &depth));
        if let Some(cs) = children.get(&id) {
            for &c in cs {
                if let Some(cnt) = pending.get_mut(&c) {
                    *cnt = cnt.saturating_sub(1);
                    if *cnt == 0 {
                        ready.insert(c);
                    }
                }
            }
        }
    }

    // Cycle remnants: single ascending-id pass from acyclic in-edges only.
    for &id in parents.keys() {
        if !depth.contains_key(&id) {
            let d = resolve(id, &depth);
            depth.insert(id, d);
        }
    }
    depth
}

/// Root ancestors (no present parents) reachable from `id`, ascending, up to
/// `max`. Iterative (no recursion). An empty result means the ancestry is a pure
/// cycle with no parentless escape — itself the anomaly, not a real root.
fn root_ids(id: i64, parents: &BTreeMap<i64, Vec<i64>>, max: usize) -> Vec<i64> {
    let mut roots: BTreeSet<i64> = BTreeSet::new();
    let mut seen: BTreeSet<i64> = BTreeSet::new();
    let mut stack = vec![id];
    while let Some(cur) = stack.pop() {
        if !seen.insert(cur) {
            continue;
        }
        match parents.get(&cur) {
            Some(ps) if !ps.is_empty() => stack.extend(ps.iter().copied()),
            _ => {
                // No present parents → a root (don't count the queried node
                // itself unless it is genuinely a parentless leaf, which is the
                // intended degenerate-root case).
                roots.insert(cur);
            }
        }
    }
    roots.into_iter().take(max).collect()
}

/// Truncate to `max` findings (0 = unlimited). Caller has already ordered them.
fn cap<T>(mut v: Vec<T>, max: usize) -> Vec<T> {
    if max > 0 && v.len() > max {
        v.truncate(max);
    }
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ev(id: i64, ts: i64, group: &str, sev: Severity) -> AuditEvent {
        AuditEvent {
            id,
            ts,
            group: group.to_string(),
            severity: sev,
            provenance: Provenance::Admitted,
            parents: Vec::new(),
            label: format!("evt/{id}"),
        }
    }

    #[test]
    fn empty_input_is_clean() {
        let r = audit(&[], &AuditConfig::default());
        assert_eq!(r.events_scanned, 0);
        assert_eq!(r.groups, 0);
        assert!(r.bursts.is_empty() && r.cascades.is_empty() && r.leaks.is_empty());
    }

    #[test]
    fn burst_fires_within_window_and_groups() {
        // 4 adverse events for actor "a" within 300s → flag; "b" stays quiet.
        let evs = vec![
            ev(1, 1000, "a", Severity::Adverse),
            ev(2, 1100, "a", Severity::Adverse),
            ev(3, 1200, "a", Severity::Adverse),
            ev(4, 1250, "a", Severity::Adverse),
            ev(5, 1260, "b", Severity::Adverse),
        ];
        let r = audit(&evs, &AuditConfig::default());
        assert_eq!(r.bursts.len(), 1);
        assert_eq!(r.bursts[0].group, "a");
        assert_eq!(r.bursts[0].count, 4);
        assert_eq!(r.bursts[0].event_ids, vec![1, 2, 3, 4]);
    }

    #[test]
    fn burst_respects_window_boundary() {
        // 4 events but spread over >300s so no single window holds 4.
        let evs = vec![
            ev(1, 1000, "a", Severity::Adverse),
            ev(2, 1200, "a", Severity::Adverse),
            ev(3, 1400, "a", Severity::Adverse),
            ev(4, 1600, "a", Severity::Adverse),
        ];
        let r = audit(&evs, &AuditConfig::default());
        assert!(r.bursts.is_empty(), "no 300s window holds all 4");
    }

    #[test]
    fn burst_ignores_below_floor() {
        // Benign/Watch events never count toward an Adverse-floor burst.
        let evs = vec![
            ev(1, 1000, "a", Severity::Watch),
            ev(2, 1010, "a", Severity::Watch),
            ev(3, 1020, "a", Severity::Benign),
            ev(4, 1030, "a", Severity::Watch),
        ];
        let r = audit(&evs, &AuditConfig::default());
        assert!(r.bursts.is_empty());
    }

    #[test]
    fn burst_floor_watch_counts_watch_and_adverse() {
        let cfg = AuditConfig {
            burst_floor: Severity::Watch,
            ..AuditConfig::default()
        };
        let evs = vec![
            ev(1, 1000, "a", Severity::Watch),
            ev(2, 1010, "a", Severity::Adverse),
            ev(3, 1020, "a", Severity::Watch),
            ev(4, 1030, "a", Severity::Adverse),
        ];
        let r = audit(&evs, &cfg);
        assert_eq!(r.bursts.len(), 1);
        assert_eq!(r.bursts[0].count, 4);
    }

    fn chain(len: i64) -> Vec<AuditEvent> {
        // id k has parent k-1: a straight lineage chain 1←2←…←len.
        (1..=len)
            .map(|k| {
                let mut e = ev(k, 1000 + k, "g", Severity::Benign);
                if k > 1 {
                    e.parents = vec![k - 1];
                }
                e
            })
            .collect()
    }

    #[test]
    fn cascade_flags_deep_chain_only() {
        // chain depth 6 at the tip; limit 6 → exactly the tip (and nothing < 6).
        let r = audit(&chain(6), &AuditConfig::default());
        assert_eq!(r.cascades.len(), 1);
        assert_eq!(r.cascades[0].event_id, 6);
        assert_eq!(r.cascades[0].depth, 6);
        assert_eq!(r.cascades[0].root_ids, vec![1]);
    }

    #[test]
    fn cascade_none_when_shallow() {
        let r = audit(&chain(5), &AuditConfig::default());
        assert!(r.cascades.is_empty());
    }

    fn with_parents(id: i64, parents: &[i64]) -> AuditEvent {
        let mut e = ev(id, 1000 + id, "g", Severity::Benign);
        e.parents = parents.to_vec();
        e
    }

    #[test]
    fn cascade_picks_longer_of_two_parent_branches() {
        // Diamond: 5 ← {3 (depth 3 via 1←2←3), 4 (depth 2 via 1←4)} → depth 4.
        let evs = vec![
            with_parents(1, &[]),
            with_parents(2, &[1]),
            with_parents(3, &[2]),
            with_parents(4, &[1]),
            with_parents(5, &[3, 4]),
        ];
        let cfg = AuditConfig {
            cascade_depth_limit: 4,
            ..AuditConfig::default()
        };
        let r = audit(&evs, &cfg);
        assert_eq!(r.cascades.len(), 1, "only node 5 reaches depth 4");
        assert_eq!(r.cascades[0].event_id, 5);
        assert_eq!(
            r.cascades[0].depth, 4,
            "longer branch (via 3) chosen, not 3"
        );
    }

    #[test]
    fn cascade_cycle_does_not_hide_a_real_deep_chain() {
        // The lensA blocker repro: cycle 1↔2 plus a deep acyclic tail
        // 1←3←4←5←6←7←8. A correct analyzer must still surface the deep chain and
        // must terminate (the old shared-memo code cached node 2 as depth 1).
        let evs = vec![
            with_parents(1, &[2, 3]),
            with_parents(2, &[1]),
            with_parents(3, &[4]),
            with_parents(4, &[5]),
            with_parents(5, &[6]),
            with_parents(6, &[7]),
            with_parents(7, &[8]),
            with_parents(8, &[]),
        ];
        let r = audit(&evs, &AuditConfig::default());
        let by_id = |id: i64| {
            r.cascades
                .iter()
                .find(|c| c.event_id == id)
                .map(|c| c.depth)
        };
        // Real DAG nodes keep their exact longest acyclic depth — none missed.
        assert_eq!(by_id(1), Some(7), "1←3←4←5←6←7←8 = 7 nodes");
        assert_eq!(
            by_id(2),
            Some(8),
            "2←1←3←…←8 = 8 nodes (was wrongly 1 before)"
        );
        assert_eq!(by_id(3), Some(6));
    }

    #[test]
    fn cascade_deep_chain_does_not_overflow() {
        // 5000-node chain — the recursive version aborted here; the iterative DP
        // computes it and reports the tip's depth correctly.
        let r = audit(&chain(5000), &AuditConfig::default());
        assert_eq!(r.cascades[0].event_id, 5000);
        assert_eq!(r.cascades[0].depth, 5000);
    }

    #[test]
    fn cascade_duplicate_id_is_order_independent() {
        // Two rows share id=2 with different parents/labels; the canonical sort
        // must pick the same winner regardless of input order.
        let root = with_parents(1, &[]);
        let mut a = with_parents(2, &[1]);
        a.label = "A".to_string();
        let mut b = with_parents(2, &[]);
        b.label = "B".to_string();
        let cfg = AuditConfig {
            cascade_depth_limit: 2,
            ..AuditConfig::default()
        };
        let fwd = audit(&[root.clone(), a.clone(), b.clone()], &cfg);
        let rev = audit(&[b, a, root], &cfg);
        assert_eq!(fwd, rev, "duplicate-id result must not depend on row order");
    }

    #[test]
    fn leak_flags_unprovenanced_and_dangling() {
        let mut a = ev(1, 1000, "g", Severity::Benign);
        a.provenance = Provenance::Unprovenanced; // un-provenanced effect
        let mut b = ev(2, 1001, "g", Severity::Benign);
        b.parents = vec![999]; // dangling: 999 not present
        let evs = vec![a, b];
        let r = audit(&evs, &AuditConfig::default());
        assert_eq!(r.leaks.len(), 2);
        assert_eq!(r.leaks[0].event_id, 1);
        assert_eq!(r.leaks[0].kind, LeakKind::Unprovenanced);
        assert_eq!(r.leaks[1].event_id, 2);
        assert_eq!(r.leaks[1].kind, LeakKind::DanglingParent);
        assert_eq!(r.leaks[1].dangling_parents, vec![999]);
    }

    #[test]
    fn present_parent_is_not_a_leak() {
        // A parent that IS in the set is lineage, not a dangling reference.
        let evs = chain(3);
        let r = audit(&evs, &AuditConfig::default());
        assert!(r.leaks.is_empty());
    }

    #[test]
    fn cap_limits_findings_per_kind() {
        // Two independent bursts; cap to 1.
        let mut evs = Vec::new();
        for (g, base) in [("a", 1000i64), ("b", 5000)] {
            for k in 0..4 {
                let id = base + k;
                evs.push(ev(id, base + k * 10, g, Severity::Adverse));
            }
        }
        let cfg = AuditConfig {
            max_findings_per_kind: 1,
            ..AuditConfig::default()
        };
        let r = audit(&evs, &cfg);
        assert_eq!(r.bursts.len(), 1);
    }

    #[test]
    fn report_is_order_independent() {
        let evs = vec![
            ev(4, 1250, "a", Severity::Adverse),
            ev(1, 1000, "a", Severity::Adverse),
            ev(3, 1200, "a", Severity::Adverse),
            ev(2, 1100, "a", Severity::Adverse),
        ];
        let mut rev = evs.clone();
        rev.reverse();
        assert_eq!(
            audit(&evs, &AuditConfig::default()),
            audit(&rev, &AuditConfig::default())
        );
    }
}
