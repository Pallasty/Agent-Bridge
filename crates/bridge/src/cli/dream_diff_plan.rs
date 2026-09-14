//! Pure differences between already acquired and validated snapshot values.

#[derive(Debug, PartialEq)]
pub(crate) struct DiffPlan<'a> {
    pub(crate) k_old: &'a str,
    pub(crate) k_new: &'a str,
    pub(crate) dt_secs: i64,
    pub(crate) active_d: i64,
    pub(crate) archived_d: i64,
    pub(crate) edges_d: i64,
    pub(crate) avg_imp_d: f64,
    pub(crate) kind_deltas: Vec<(String, i64, i64)>,
    pub(crate) coact_total_d: i64,
    pub(crate) coact_burst_d: i64,
    pub(crate) coact_persist_d: i64,
    pub(crate) entered_top: Vec<(String, i64)>,
    pub(crate) dropped_top: Vec<(String, i64)>,
    pub(crate) access_changed: Vec<(String, i64, i64)>,
    pub(crate) tools_d: i64,
    pub(crate) saves_d: i64,
    pub(crate) topo_total_d: i64,
    pub(crate) topo_orphan_d: i64,
    pub(crate) topo_p4_d: i64,
    pub(crate) hubs_entered: Vec<(String, i64)>,
    pub(crate) hubs_dropped: Vec<(String, i64)>,
    pub(crate) trans_entered: Vec<(String, String, i64)>,
    pub(crate) trans_dropped: Vec<(String, String, i64)>,
}

pub(crate) fn calculate<'a>(
    pa: serde_json::Value,
    pb: serde_json::Value,
    key_a: &'a str,
    key_b: &'a str,
) -> DiffPlan<'a> {
    // Auto-order: smaller captured_at = older.
    let ts_a = pa.get("captured_at").and_then(|v| v.as_i64()).unwrap_or(0);
    let ts_b = pb.get("captured_at").and_then(|v| v.as_i64()).unwrap_or(0);
    let ((older, k_old, ts_old), (newer, k_new, ts_new)) = if ts_a <= ts_b {
        ((&pa, key_a, ts_a), (&pb, key_b, ts_b))
    } else {
        ((&pb, key_b, ts_b), (&pa, key_a, ts_a))
    };
    let dt_secs = (ts_new - ts_old).max(0);

    // Helpers to extract numbers, with 0 fallback.
    let gi64 = |v: &serde_json::Value, path: &[&str]| -> i64 {
        let mut cur = v;
        for p in path {
            cur = match cur.get(*p) {
                Some(x) => x,
                None => return 0,
            };
        }
        cur.as_i64()
            .or_else(|| cur.as_u64().map(|u| u as i64))
            .unwrap_or(0)
    };
    let gf64 = |v: &serde_json::Value, path: &[&str]| -> f64 {
        let mut cur = v;
        for p in path {
            cur = match cur.get(*p) {
                Some(x) => x,
                None => return 0.0,
            };
        }
        cur.as_f64().unwrap_or(0.0)
    };

    // memory.* deltas
    let active_d =
        gi64(newer, &["memory", "active_total"]) - gi64(older, &["memory", "active_total"]);
    let archived_d =
        gi64(newer, &["memory", "archived_total"]) - gi64(older, &["memory", "archived_total"]);
    let edges_d = gi64(newer, &["memory", "edge_count"]) - gi64(older, &["memory", "edge_count"]);
    let avg_imp_d = gf64(newer, &["memory", "avg_importance_active"])
        - gf64(older, &["memory", "avg_importance_active"]);

    // by_kind deltas — diff per kind name. Use HashMap to align.
    let by_kind_old: std::collections::HashMap<String, i64> =
        kind_map(older.get("memory").and_then(|m| m.get("by_kind_non_skill")));
    let by_kind_new: std::collections::HashMap<String, i64> =
        kind_map(newer.get("memory").and_then(|m| m.get("by_kind_non_skill")));
    let kinds_union: std::collections::BTreeSet<String> = by_kind_old
        .keys()
        .chain(by_kind_new.keys())
        .cloned()
        .collect();
    let kind_deltas: Vec<(String, i64, i64)> = kinds_union
        .iter()
        .filter_map(|k| {
            let o = by_kind_old.get(k).copied().unwrap_or(0);
            let n = by_kind_new.get(k).copied().unwrap_or(0);
            if o != n {
                Some((k.clone(), o, n))
            } else {
                None
            }
        })
        .collect();

    // coactivation.* deltas
    let coact_total_d = gi64(newer, &["coactivation", "total_pairs"])
        - gi64(older, &["coactivation", "total_pairs"]);
    let coact_burst_d = gi64(newer, &["coactivation", "pairs_burst_lt_1h"])
        - gi64(older, &["coactivation", "pairs_burst_lt_1h"]);
    let coact_persist_d = gi64(newer, &["coactivation", "pairs_persistent_ge_6h"])
        - gi64(older, &["coactivation", "pairs_persistent_ge_6h"]);

    // access.top_10_keys deltas — which keys entered/left, and access_count changes
    let access_old: std::collections::HashMap<String, i64> =
        access_map(older.get("access").and_then(|a| a.get("top_10_keys")));
    let access_new: std::collections::HashMap<String, i64> =
        access_map(newer.get("access").and_then(|a| a.get("top_10_keys")));
    let entered_top: Vec<(String, i64)> = access_new
        .iter()
        .filter(|(k, _)| !access_old.contains_key(*k))
        .map(|(k, n)| (k.clone(), *n))
        .collect();
    let dropped_top: Vec<(String, i64)> = access_old
        .iter()
        .filter(|(k, _)| !access_new.contains_key(*k))
        .map(|(k, n)| (k.clone(), *n))
        .collect();
    let access_changed: Vec<(String, i64, i64)> = access_new
        .iter()
        .filter_map(|(k, n)| {
            access_old.get(k).and_then(|o| {
                if o != n {
                    Some((k.clone(), *o, *n))
                } else {
                    None
                }
            })
        })
        .collect();

    // identity.{current,prior}.tool_calls_total + memory_saves deltas
    let tools_d = gi64(newer, &["identity", "current", "tool_calls_total"])
        - gi64(older, &["identity", "current", "tool_calls_total"]);
    let saves_d = gi64(newer, &["identity", "current", "memory_saves"])
        - gi64(older, &["identity", "current", "memory_saves"]);

    // ζ-9 — topology deltas (v1 snapshots default to 0/empty via gi64).
    let topo_total_d = gi64(newer, &["topology", "non_skill_active_total"])
        - gi64(older, &["topology", "non_skill_active_total"]);
    let topo_orphan_d =
        gi64(newer, &["topology", "orphan_count"]) - gi64(older, &["topology", "orphan_count"]);
    let topo_p4_d = gi64(newer, &["topology", "p4_evolved_coverage"])
        - gi64(older, &["topology", "p4_evolved_coverage"]);
    // Hub set diff — which keys entered/left top-5 hubs.
    let hub_set = |v: Option<&serde_json::Value>| -> Vec<(String, i64)> {
        let mut out = Vec::new();
        if let Some(arr) = v.and_then(|x| x.as_array()) {
            for item in arr {
                if let (Some(k), Some(d)) = (
                    item.get("key").and_then(|x| x.as_str()),
                    item.get("degree").and_then(|x| x.as_i64()),
                ) {
                    out.push((k.to_string(), d));
                }
            }
        }
        out
    };
    let hubs_old = hub_set(older.get("topology").and_then(|t| t.get("top_5_hubs")));
    let hubs_new = hub_set(newer.get("topology").and_then(|t| t.get("top_5_hubs")));
    let hubs_entered: Vec<(String, i64)> = hubs_new
        .iter()
        .filter(|(k, _)| !hubs_old.iter().any(|(x, _)| x == k))
        .cloned()
        .collect();
    let hubs_dropped: Vec<(String, i64)> = hubs_old
        .iter()
        .filter(|(k, _)| !hubs_new.iter().any(|(x, _)| x == k))
        .cloned()
        .collect();

    // transitions.top_5 — entered/left
    let trans_old = trans_set(older.get("transitions").and_then(|t| t.get("top_5")));
    let trans_new = trans_set(newer.get("transitions").and_then(|t| t.get("top_5")));
    let trans_entered: Vec<(String, String, i64)> = trans_new
        .iter()
        .filter(|(a, b, _)| !trans_old.iter().any(|(x, y, _)| x == a && y == b))
        .cloned()
        .collect();
    let trans_dropped: Vec<(String, String, i64)> = trans_old
        .iter()
        .filter(|(a, b, _)| !trans_new.iter().any(|(x, y, _)| x == a && y == b))
        .cloned()
        .collect();

    DiffPlan {
        k_old,
        k_new,
        dt_secs,
        active_d,
        archived_d,
        edges_d,
        avg_imp_d,
        kind_deltas,
        coact_total_d,
        coact_burst_d,
        coact_persist_d,
        entered_top,
        dropped_top,
        access_changed,
        tools_d,
        saves_d,
        topo_total_d,
        topo_orphan_d,
        topo_p4_d,
        hubs_entered,
        hubs_dropped,
        trans_entered,
        trans_dropped,
    }
}

fn kind_map(v: Option<&serde_json::Value>) -> std::collections::HashMap<String, i64> {
    let mut m = std::collections::HashMap::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(k), Some(n)) = (
                item.get("kind").and_then(|x| x.as_str()),
                item.get("count").and_then(|x| x.as_i64()),
            ) {
                m.insert(k.to_string(), n);
            }
        }
    }
    m
}

fn access_map(v: Option<&serde_json::Value>) -> std::collections::HashMap<String, i64> {
    let mut m = std::collections::HashMap::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(k), Some(n)) = (
                item.get("key").and_then(|x| x.as_str()),
                item.get("access_count").and_then(|x| x.as_i64()),
            ) {
                m.insert(k.to_string(), n);
            }
        }
    }
    m
}

fn trans_set(v: Option<&serde_json::Value>) -> Vec<(String, String, i64)> {
    let mut out = Vec::new();
    if let Some(arr) = v.and_then(|x| x.as_array()) {
        for item in arr {
            if let (Some(a), Some(b), Some(n)) = (
                item.get("from").and_then(|x| x.as_str()),
                item.get("to").and_then(|x| x.as_str()),
                item.get("count").and_then(|x| x.as_i64()),
            ) {
                out.push((a.to_string(), b.to_string(), n));
            }
        }
    }
    out
}
