//! Connectivity-repair candidate generator — read-only graph-island bridge
//! proposals (borrow T8/P4).
//!
//! ## Problem
//! AB detects graph components (e.g. `hebbian_clusters`, a Union-Find over the
//! `cofires`/`co_referenced` subset of `memory_edges`) but has **no repair
//! step**: orphan islands persist, and `memory_neighbors_bfs` — which traverses
//! the *full* `memory_edges` graph undirected — cannot cross a cut, so
//! spreading-activation recall degrades across disconnected fragments (the 60%
//! orphan rate that `finding_graph_orphan_topology_20260511` surfaced). This
//! analyzer uses that same full-edge graph (broader than hebbian_clusters'
//! subset, so component counts differ from it by design).
//!
//! ## Borrow
//! `TCF/src/core/neural_plasticity.py::_optimize_topology` stitches fragmented
//! topology — but pairs islands with `np.random`, which is the **anti-pattern**
//! (non-reproducible, sync-hostile). This port keeps the *idea* (bridge islands
//! to the mainland) and makes it **deterministic**: a bridge target is chosen by
//! (shared-tag overlap, importance, key) — never randomly.
//!
//! ## Discipline (mirrors [`crate::quant`] / [`crate::coactivation_latch`])
//! - **Read-only / shadow.** This only *proposes* bridge edges; it never writes.
//!   Any real edge goes through the `memory_related_keys_materialize`
//!   propose→review→materialize ladder. The DB-agnostic core operates on plain
//!   [`GraphNode`]/[`GraphEdge`] values; the read-only SQLite read lives in
//!   `examples/connectivity_repair_eval.rs`.
//! - **Deterministic.** No RNG, no clock, no `HashMap` iteration — `BTree*`
//!   throughout, every tie broken by key, and duplicate node keys resolved by
//!   importance (not input order). Same node/edge set → identical proposals.

use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;

/// A memory node in the connectivity graph.
#[derive(Debug, Clone, PartialEq)]
pub struct GraphNode {
    /// Memory key.
    pub key: String,
    /// Cognitive importance (0.0–1.0) — used to rank bridge targets.
    pub importance: f64,
    /// Tags — the overlap basis for choosing a semantically-related bridge.
    pub tags: Vec<String>,
}

/// An undirected edge between two memory keys (direction is ignored for
/// connectivity — `memory_edges` rows are folded into an undirected graph).
#[derive(Debug, Clone, PartialEq)]
pub struct GraphEdge {
    pub from: String,
    pub to: String,
}

/// Tuning for [`analyze`].
#[derive(Debug, Clone)]
pub struct RepairConfig {
    /// Only propose a bridge for a non-mainland component whose size is `<=`
    /// this. Default [`usize::MAX`] = bridge every island regardless of size.
    pub max_island_size: usize,
    /// Cap on candidates returned (0 = unlimited). Candidates are ordered
    /// smallest-island-first, so a cap keeps the most-isolated nodes.
    pub max_candidates: usize,
}

impl Default for RepairConfig {
    fn default() -> Self {
        Self {
            max_island_size: usize::MAX,
            max_candidates: 0,
        }
    }
}

/// One proposed bridge edge: connect `orphan_key` (an island representative)
/// to `bridge_to` (a mainland hub). **A proposal only — never written.**
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct RepairCandidate {
    /// The island representative to connect (highest-importance node of its
    /// component; for a degree-0 orphan, the node itself).
    pub orphan_key: String,
    /// The proposed mainland target (best shared-tag / highest-importance hub).
    pub bridge_to: String,
    /// Size of `orphan_key`'s component (1 = a fully isolated orphan).
    pub component_size: usize,
    /// Tags shared by the orphan and the target — the semantic basis (sorted).
    pub shared_tags: Vec<String>,
    /// Importance of the chosen target.
    pub target_importance: f64,
    /// Human-readable basis string.
    pub reason: String,
}

/// Read-only connectivity report + bridge proposals.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ConnectivityReport {
    /// Nodes considered.
    pub nodes: usize,
    /// Qualifying undirected edge **rows** (self-loops and dangling edges
    /// dropped; duplicate / both-direction rows are each counted — a row tally,
    /// not a distinct-edge count). Connectivity itself is unaffected.
    pub edges: usize,
    /// Connected-component count.
    pub components: usize,
    /// Size of the largest component (the "mainland").
    pub largest_component_size: usize,
    /// Degree-0 nodes (isolated orphans).
    pub orphan_nodes: usize,
    /// Non-mainland components (islands) — the repair targets.
    pub island_components: usize,
    /// Deterministic bridge proposals, smallest-island-first.
    pub candidates: Vec<RepairCandidate>,
}

/// Analyze a memory graph and propose deterministic bridge edges that stitch
/// every island to the mainland. Read-only: returns proposals, writes nothing.
///
/// A bridge is proposed only when a real **mainland** exists
/// (`largest_component_size >= 2`); a fully-disconnected graph has no anchor to
/// stitch to and yields no candidates.
pub fn analyze(nodes: &[GraphNode], edges: &[GraphEdge], cfg: &RepairConfig) -> ConnectivityReport {
    // Stable node ordering + key→index for an index-based Union-Find.
    let index: BTreeMap<&str, usize> = {
        let mut keys: BTreeSet<&str> = BTreeSet::new();
        for n in nodes {
            keys.insert(n.key.as_str());
        }
        keys.into_iter().enumerate().map(|(i, k)| (k, i)).collect()
    };
    let n = index.len();
    // Deterministic on duplicate keys: keep the higher-importance node
    // (tie-break by larger tag list), so output never depends on input order.
    let mut by_key: BTreeMap<&str, &GraphNode> = BTreeMap::new();
    for x in nodes {
        match by_key.get(x.key.as_str()) {
            Some(cur) if !node_supersedes(x, cur) => {}
            _ => {
                by_key.insert(x.key.as_str(), x);
            }
        }
    }

    let mut uf = UnionFind::new(n);
    let mut edge_count = 0usize;
    let mut degree: BTreeMap<&str, usize> = BTreeMap::new();
    for e in edges {
        if e.from == e.to {
            continue; // self-loop: irrelevant to connectivity
        }
        if let (Some(&a), Some(&b)) = (index.get(e.from.as_str()), index.get(e.to.as_str())) {
            uf.union(a, b);
            edge_count += 1;
            *degree.entry(e.from.as_str()).or_default() += 1;
            *degree.entry(e.to.as_str()).or_default() += 1;
        }
        // dangling edge (endpoint not in node set) is ignored
    }

    // Group keys by component root (BTreeMap keeps the grouping deterministic).
    let mut comps: BTreeMap<usize, BTreeSet<&str>> = BTreeMap::new();
    for (k, &i) in &index {
        comps.entry(uf.find(i)).or_default().insert(k);
    }

    // Mainland = largest component; tie-break by total importance, then by
    // smallest member key — fully deterministic.
    let mainland_root = comps.iter().max_by(|(_, a), (_, b)| {
        a.len()
            .cmp(&b.len())
            .then_with(|| comp_importance(a, &by_key).total_cmp(&comp_importance(b, &by_key)))
            .then_with(|| b.iter().next().cmp(&a.iter().next())) // smaller key wins → reverse
    });
    let largest_component_size = mainland_root.map(|(_, m)| m.len()).unwrap_or(0);
    let mainland_root = mainland_root.map(|(r, _)| *r);

    // Every entry in `degree` has count >= 1, so degree-0 orphans are exactly
    // the nodes that never appeared in a valid edge.
    let orphan_nodes = n - degree.len();

    // Propose one bridge per non-mainland component, only if a real mainland
    // (size >= 2) exists.
    let mut candidates: Vec<RepairCandidate> = Vec::new();
    let mut island_components = 0usize;
    if largest_component_size >= 2 {
        let mainland_root = mainland_root.expect("mainland exists when size>=2");
        let mainland: &BTreeSet<&str> = &comps[&mainland_root];
        for (&root, members) in &comps {
            if root == mainland_root {
                continue;
            }
            island_components += 1;
            if members.len() > cfg.max_island_size {
                continue;
            }
            // Island representative: highest importance, tie-break smallest key.
            let rep = members
                .iter()
                .max_by(|a, b| {
                    importance_of(a, &by_key)
                        .total_cmp(&importance_of(b, &by_key))
                        .then_with(|| b.cmp(a)) // smaller key wins
                })
                .copied()
                .expect("non-empty component");
            let rep_tags: BTreeSet<&str> = by_key
                .get(rep)
                .map(|node| node.tags.iter().map(|t| t.as_str()).collect())
                .unwrap_or_default();

            // Target in mainland: maximize (shared-tag count, importance),
            // tie-break smallest key.
            let target = mainland
                .iter()
                .max_by(|a, b| {
                    shared_count(a, &rep_tags, &by_key)
                        .cmp(&shared_count(b, &rep_tags, &by_key))
                        .then_with(|| {
                            importance_of(a, &by_key).total_cmp(&importance_of(b, &by_key))
                        })
                        .then_with(|| b.cmp(a))
                })
                .copied()
                .expect("non-empty mainland");

            let shared_tags: Vec<String> = shared_tags(target, &rep_tags, &by_key);
            let target_importance = importance_of(target, &by_key);
            let reason = if !shared_tags.is_empty() {
                format!(
                    "island(size={}) → mainland hub by {} shared tag(s)",
                    members.len(),
                    shared_tags.len()
                )
            } else {
                format!(
                    "island(size={}) → highest-importance mainland hub (no shared tags)",
                    members.len()
                )
            };
            candidates.push(RepairCandidate {
                orphan_key: rep.to_string(),
                bridge_to: target.to_string(),
                component_size: members.len(),
                shared_tags,
                target_importance,
                reason,
            });
        }
    } else {
        // No mainland (largest component < 2): every component is a singleton,
        // so there is nothing to anchor a bridge to → no candidates. All
        // components count as islands (reporting-only).
        island_components = comps.len();
    }

    // Order smallest-island-first (most isolated), then by key; apply cap.
    candidates.sort_by(|a, b| {
        a.component_size
            .cmp(&b.component_size)
            .then_with(|| a.orphan_key.cmp(&b.orphan_key))
    });
    if cfg.max_candidates > 0 && candidates.len() > cfg.max_candidates {
        candidates.truncate(cfg.max_candidates);
    }

    ConnectivityReport {
        nodes: n,
        edges: edge_count,
        components: comps.len(),
        largest_component_size,
        orphan_nodes,
        island_components,
        candidates,
    }
}

/// Deterministic duplicate-key tie-break: does `a` supersede `b` as the
/// canonical node for a shared key? Higher importance wins; on an importance
/// tie, the larger tag list (lexicographic) wins — independent of input order.
fn node_supersedes(a: &GraphNode, b: &GraphNode) -> bool {
    match a.importance.total_cmp(&b.importance) {
        std::cmp::Ordering::Greater => true,
        std::cmp::Ordering::Less => false,
        std::cmp::Ordering::Equal => a.tags > b.tags,
    }
}

fn importance_of(key: &str, by_key: &BTreeMap<&str, &GraphNode>) -> f64 {
    by_key.get(key).map(|n| n.importance).unwrap_or(0.0)
}

fn comp_importance(members: &BTreeSet<&str>, by_key: &BTreeMap<&str, &GraphNode>) -> f64 {
    members.iter().map(|k| importance_of(k, by_key)).sum()
}

fn shared_count(
    key: &str,
    rep_tags: &BTreeSet<&str>,
    by_key: &BTreeMap<&str, &GraphNode>,
) -> usize {
    by_key
        .get(key)
        .map(|n| {
            n.tags
                .iter()
                .filter(|t| rep_tags.contains(t.as_str()))
                .count()
        })
        .unwrap_or(0)
}

fn shared_tags(
    key: &str,
    rep_tags: &BTreeSet<&str>,
    by_key: &BTreeMap<&str, &GraphNode>,
) -> Vec<String> {
    let mut out: BTreeSet<String> = BTreeSet::new();
    if let Some(n) = by_key.get(key) {
        for t in &n.tags {
            if rep_tags.contains(t.as_str()) {
                out.insert(t.clone());
            }
        }
    }
    out.into_iter().collect()
}

/// Index-based Union-Find with path-halving + union-by-size. Deterministic.
struct UnionFind {
    parent: Vec<usize>,
    size: Vec<usize>,
}

impl UnionFind {
    fn new(n: usize) -> Self {
        Self {
            parent: (0..n).collect(),
            size: vec![1; n],
        }
    }
    fn find(&mut self, mut x: usize) -> usize {
        while self.parent[x] != x {
            self.parent[x] = self.parent[self.parent[x]]; // path halving
            x = self.parent[x];
        }
        x
    }
    fn union(&mut self, a: usize, b: usize) {
        let (ra, rb) = (self.find(a), self.find(b));
        if ra == rb {
            return;
        }
        // union by size; tie-break to the smaller root index for determinism.
        let (big, small) =
            if self.size[ra] > self.size[rb] || (self.size[ra] == self.size[rb] && ra < rb) {
                (ra, rb)
            } else {
                (rb, ra)
            };
        self.parent[small] = big;
        self.size[big] += self.size[small];
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(key: &str, importance: f64, tags: &[&str]) -> GraphNode {
        GraphNode {
            key: key.to_string(),
            importance,
            tags: tags.iter().map(|s| s.to_string()).collect(),
        }
    }
    fn edge(from: &str, to: &str) -> GraphEdge {
        GraphEdge {
            from: from.to_string(),
            to: to.to_string(),
        }
    }

    // mainland a-b-c, island d-e, isolated orphan f.
    fn fixture() -> (Vec<GraphNode>, Vec<GraphEdge>) {
        let nodes = vec![
            node("a", 0.9, &["rust", "graph"]),
            node("b", 0.5, &["rust"]),
            node("c", 0.4, &["graph"]),
            node("d", 0.7, &["rust"]),
            node("e", 0.3, &["misc"]),
            node("f", 0.6, &["graph"]),
        ];
        let edges = vec![edge("a", "b"), edge("b", "c"), edge("d", "e")];
        (nodes, edges)
    }

    #[test]
    fn detects_components_and_orphans() {
        let (nodes, edges) = fixture();
        let r = analyze(&nodes, &edges, &RepairConfig::default());
        assert_eq!(r.nodes, 6);
        assert_eq!(r.edges, 3);
        assert_eq!(r.components, 3); // {a,b,c} {d,e} {f}
        assert_eq!(r.largest_component_size, 3);
        assert_eq!(r.orphan_nodes, 1); // f
        assert_eq!(r.island_components, 2); // {d,e} and {f}
    }

    #[test]
    fn proposes_one_bridge_per_island_smallest_first() {
        let (nodes, edges) = fixture();
        let r = analyze(&nodes, &edges, &RepairConfig::default());
        assert_eq!(r.candidates.len(), 2);
        // smallest island first: the isolated orphan f (size 1) before {d,e} (size 2)
        assert_eq!(r.candidates[0].orphan_key, "f");
        assert_eq!(r.candidates[0].component_size, 1);
        assert_eq!(r.candidates[1].component_size, 2);
        // {d,e} representative is d (importance 0.7 > e 0.3)
        assert_eq!(r.candidates[1].orphan_key, "d");
    }

    #[test]
    fn bridge_target_prefers_shared_tags() {
        let (nodes, edges) = fixture();
        let r = analyze(&nodes, &edges, &RepairConfig::default());
        // f has tag "graph"; mainland nodes: a{rust,graph}, c{graph} share it,
        // b{rust} doesn't. a and c both share 1 tag → tie broken by importance:
        // a (0.9) > c (0.4) → target a.
        let f = &r.candidates[0];
        assert_eq!(f.orphan_key, "f");
        assert_eq!(f.bridge_to, "a");
        assert_eq!(f.shared_tags, vec!["graph".to_string()]);
        // d has tag "rust"; mainland a{..rust}, b{rust} share it. Tie → importance
        // a(0.9) > b(0.5) → target a.
        let d = &r.candidates[1];
        assert_eq!(d.bridge_to, "a");
        assert_eq!(d.shared_tags, vec!["rust".to_string()]);
    }

    #[test]
    fn deterministic_across_runs_and_input_order() {
        let (mut nodes, mut edges) = fixture();
        let r1 = analyze(&nodes, &edges, &RepairConfig::default());
        nodes.reverse();
        edges.reverse();
        let r2 = analyze(&nodes, &edges, &RepairConfig::default());
        assert_eq!(r1, r2);
    }

    #[test]
    fn no_mainland_yields_no_candidates() {
        // all isolated → no component >= 2 → nothing to anchor to.
        let nodes = vec![node("a", 0.9, &["x"]), node("b", 0.5, &["x"])];
        let r = analyze(&nodes, &[], &RepairConfig::default());
        assert_eq!(r.components, 2);
        assert_eq!(r.largest_component_size, 1);
        assert_eq!(r.orphan_nodes, 2);
        assert!(r.candidates.is_empty());
    }

    #[test]
    fn max_island_size_filters_large_islands() {
        let (nodes, edges) = fixture();
        let cfg = RepairConfig {
            max_island_size: 1, // only isolated orphans, skip the {d,e} island
            max_candidates: 0,
        };
        let r = analyze(&nodes, &edges, &cfg);
        assert_eq!(r.island_components, 2); // still counts both
        assert_eq!(r.candidates.len(), 1); // but only f proposed
        assert_eq!(r.candidates[0].orphan_key, "f");
    }

    #[test]
    fn max_candidates_caps_keeping_smallest_islands() {
        let (nodes, edges) = fixture();
        let cfg = RepairConfig {
            max_island_size: usize::MAX,
            max_candidates: 1,
        };
        let r = analyze(&nodes, &edges, &cfg);
        assert_eq!(r.candidates.len(), 1);
        assert_eq!(r.candidates[0].orphan_key, "f"); // smallest island kept
    }

    #[test]
    fn self_loops_and_dangling_edges_ignored() {
        let nodes = vec![
            node("a", 0.9, &["x"]),
            node("b", 0.5, &["x"]),
            node("c", 0.4, &["x"]),
        ];
        let edges = vec![
            edge("a", "a"),     // self-loop
            edge("a", "b"),     // real
            edge("b", "ghost"), // dangling (ghost not a node)
        ];
        let r = analyze(&nodes, &edges, &RepairConfig::default());
        assert_eq!(r.edges, 1); // only a-b counts
        assert_eq!(r.components, 2); // {a,b} and {c}
        assert_eq!(r.candidates.len(), 1);
        assert_eq!(r.candidates[0].orphan_key, "c");
        assert_eq!(r.candidates[0].bridge_to, "a"); // a(0.9) > b(0.5)
    }

    #[test]
    fn empty_graph_is_safe() {
        let r = analyze(&[], &[], &RepairConfig::default());
        assert_eq!(r.nodes, 0);
        assert_eq!(r.components, 0);
        assert_eq!(r.largest_component_size, 0);
        assert!(r.candidates.is_empty());
    }

    #[test]
    fn duplicate_keys_resolve_independent_of_input_order() {
        // Same two 'z' entries in either order → identical output; the
        // higher-importance copy (0.8, tags ["y"]) wins deterministically.
        let edges = vec![edge("a", "b"), edge("b", "c")];
        let base = || {
            vec![
                node("a", 0.9, &["y"]),
                node("b", 0.5, &["y"]),
                node("c", 0.4, &["y"]),
            ]
        };
        let za = node("z", 0.2, &["x"]);
        let zb = node("z", 0.8, &["y"]);
        let mut s1 = base();
        s1.push(za.clone());
        s1.push(zb.clone());
        let mut s2 = base();
        s2.push(zb.clone());
        s2.push(za.clone());
        let r1 = analyze(&s1, &edges, &RepairConfig::default());
        let r2 = analyze(&s2, &edges, &RepairConfig::default());
        assert_eq!(r1, r2);
        assert_eq!(r1.candidates.len(), 1);
        assert_eq!(r1.candidates[0].orphan_key, "z");
        // winner zb shares tag "y"; target by importance among mainland = a
        assert_eq!(r1.candidates[0].shared_tags, vec!["y".to_string()]);
        assert_eq!(r1.candidates[0].bridge_to, "a");
    }
}
