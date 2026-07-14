//! Public, synthetic admission fixture for the frozen reference surface.
//!
//! This example creates three fresh temporary SQLite clones from the same
//! content-free fixture, changing only memory/edge insertion order. It checks
//! that the read-only reference projection is invariant to that order, that
//! graph expansion is bounded, that the skill kind is excluded, that frozen
//! as-of replay is stable at the timestamp boundary, and that graph reads do
//! not mutate access telemetry. It never opens the owner store or emits a
//! generator-facing runtime authorization.

use ab_store::{
    ImportConflictPolicy, MemoryEdgeExport, MemoryPeekResult, MemoryRecord,
    MemorySearchReferenceContext, MemorySearchReferenceOptions, SqliteStore, StateStore,
};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

const SCHEMA: &str = "agent_bridge.store.memory_reference_admission_fixture.v1";
const SENTINEL_ENVS: [&str; 3] = [
    "AB_REFERENCE_ADMISSION_SENTINEL",
    "AGENT_BRIDGE_REFERENCE_ADMISSION_SENTINEL",
    "RUST_LOG",
];

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Fixture {
    schema: String,
    fixture_only: bool,
    real_capture_authorized: bool,
    as_of_secs: i64,
    record_timestamp: i64,
    ttl_boundary_secs: i64,
    query: String,
    limit: u32,
    rrf_k: f64,
    expand_top: u32,
    graph_fanout: usize,
    max_context_bytes: usize,
    exclude_kinds: Vec<String>,
    records: Vec<MemoryRecord>,
    edges: Vec<MemoryEdgeExport>,
    coactivations: Vec<CoactivationSpec>,
    expected: Expected,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CoactivationSpec {
    key_a: String,
    key_b: String,
    count: u32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Expected {
    tie_order: Vec<String>,
    seed_context_keys: Vec<String>,
    ttl_before_boundary_keys: Vec<String>,
    ttl_at_boundary_keys: Vec<String>,
}

#[derive(Debug, Serialize)]
struct SyncEnvelope<'a> {
    #[serde(flatten)]
    record: &'a MemoryRecord,
    version_vector: &'static str,
}

#[derive(Debug, Clone, PartialEq)]
struct Observation {
    seed_context: MemorySearchReferenceContext,
    tie_order: Vec<String>,
    ttl_before_boundary_order: Vec<String>,
    ttl_at_boundary_order: Vec<String>,
    telemetry_unchanged: bool,
    coactivation_rerank_changed_order: bool,
}

fn boxed_error(message: impl Into<String>) -> Box<dyn std::error::Error> {
    message.into().into()
}

fn validate_fixture(fixture: &Fixture) -> Result<(), Box<dyn std::error::Error>> {
    if fixture.schema != SCHEMA {
        return Err(boxed_error(format!(
            "fixture schema must be {SCHEMA}, got {}",
            fixture.schema
        )));
    }
    if !fixture.fixture_only || fixture.real_capture_authorized {
        return Err(boxed_error(
            "fixture must be synthetic-only and real_capture_authorized=false",
        ));
    }
    if fixture.as_of_secs < 0 || fixture.record_timestamp < 0 {
        return Err(boxed_error("fixture timestamps must be non-negative"));
    }
    if fixture.ttl_boundary_secs <= 0 {
        return Err(boxed_error("ttl_boundary_secs must be positive"));
    }
    if fixture.as_of_secs
        != fixture
            .record_timestamp
            .saturating_add(fixture.ttl_boundary_secs)
    {
        return Err(boxed_error(
            "as_of_secs must equal record_timestamp + ttl_boundary_secs",
        ));
    }
    if fixture.query.trim().is_empty() {
        return Err(boxed_error("fixture query must be non-empty"));
    }
    if !(1..=40).contains(&fixture.limit)
        || !(1..=20).contains(&fixture.expand_top)
        || !(1..=256).contains(&fixture.graph_fanout)
        || !(2..=16 * 1024 * 1024).contains(&fixture.max_context_bytes)
        || !fixture.rrf_k.is_finite()
        || !(1.0..=200.0).contains(&fixture.rrf_k)
    {
        return Err(boxed_error(
            "fixture search bounds are outside the public contract",
        ));
    }
    if fixture.exclude_kinds != ["skill"] {
        return Err(boxed_error("fixture must exclude exactly the skill kind"));
    }

    let mut keys = HashSet::new();
    for record in &fixture.records {
        if record.key.trim().is_empty() || !keys.insert(record.key.clone()) {
            return Err(boxed_error(
                "fixture memory keys must be unique and non-empty",
            ));
        }
        if record.created_at != fixture.record_timestamp
            || record.updated_at != fixture.record_timestamp
        {
            return Err(boxed_error(format!(
                "record {} is not bound to record_timestamp",
                record.key
            )));
        }
    }
    let key_set = keys;
    for edge in &fixture.edges {
        if !key_set.contains(&edge.from_key) || !key_set.contains(&edge.to_key) {
            return Err(boxed_error(format!(
                "edge {} -> {} has a missing endpoint",
                edge.from_key, edge.to_key
            )));
        }
        if !edge.weight.is_finite() || edge.weight < 0.0 {
            return Err(boxed_error(
                "fixture edge weights must be finite and non-negative",
            ));
        }
    }
    for edge in &fixture.coactivations {
        if !key_set.contains(&edge.key_a)
            || !key_set.contains(&edge.key_b)
            || edge.key_a == edge.key_b
            || edge.count == 0
            || edge.count > 1_000
        {
            return Err(boxed_error(
                "coactivation rows must bind distinct present endpoints and count 1..=1000",
            ));
        }
    }

    let find = |key: &str| {
        fixture
            .records
            .iter()
            .find(|record| record.key == key)
            .ok_or_else(|| boxed_error(format!("fixture is missing {key}")))
    };
    let ttl_at = find("ttl_boundary")?;
    let ttl_after = find("ttl_after_boundary")?;
    if ttl_at.tags != ["ttl:1d"] || ttl_after.tags != ["ttl:2d"] {
        return Err(boxed_error(
            "TTL controls must bind ttl:1d at the boundary and ttl:2d after it",
        ));
    }
    if ttl_at.last_accessed_at != fixture.as_of_secs
        || ttl_after.last_accessed_at
            != fixture
                .as_of_secs
                .saturating_sub(fixture.ttl_boundary_secs + 1)
    {
        return Err(boxed_error("TTL/as-of boundary records are not exact"));
    }
    for key in fixture
        .expected
        .tie_order
        .iter()
        .chain(fixture.expected.seed_context_keys.iter())
        .chain(fixture.expected.ttl_before_boundary_keys.iter())
        .chain(fixture.expected.ttl_at_boundary_keys.iter())
    {
        if !key_set.contains(key) {
            return Err(boxed_error(format!("expected key {key} is not in records")));
        }
    }
    Ok(())
}

async fn write_clone_inputs(
    clone_root: &Path,
    fixture: &Fixture,
    reverse: bool,
) -> Result<(PathBuf, PathBuf, PathBuf), Box<dyn std::error::Error>> {
    tokio::fs::create_dir_all(clone_root).await?;
    let db_path = clone_root.join("state.db");
    let memories_path = clone_root.join("memories.jsonl");
    let edges_path = clone_root.join("edges.jsonl");

    let mut record_indices: Vec<usize> = (0..fixture.records.len()).collect();
    let mut edge_indices: Vec<usize> = (0..fixture.edges.len()).collect();
    if reverse {
        record_indices.reverse();
        edge_indices.reverse();
    }

    let mut memories = String::new();
    for index in record_indices {
        let envelope = SyncEnvelope {
            record: &fixture.records[index],
            version_vector: "",
        };
        memories.push_str(&serde_json::to_string(&envelope)?);
        memories.push('\n');
    }
    tokio::fs::write(&memories_path, memories).await?;

    let mut edges = String::new();
    for index in edge_indices {
        edges.push_str(&serde_json::to_string(&fixture.edges[index])?);
        edges.push('\n');
    }
    tokio::fs::write(&edges_path, edges).await?;
    Ok((db_path, memories_path, edges_path))
}

async fn build_clone(
    clone_root: &Path,
    fixture: &Fixture,
    reverse: bool,
) -> Result<SqliteStore, Box<dyn std::error::Error>> {
    if tokio::fs::try_exists(clone_root).await? {
        tokio::fs::remove_dir_all(clone_root).await?;
    }
    let (db_path, memories_path, edges_path) =
        write_clone_inputs(clone_root, fixture, reverse).await?;
    let store = SqliteStore::open(&db_path).await?;
    let report = store
        .memory_import(
            &memories_path,
            ImportConflictPolicy::Skip,
            Some(&edges_path),
        )
        .await?;
    if report.inserted != fixture.records.len() as u64
        || report.edges_upserted != fixture.edges.len() as u64
        || report.malformed != 0
        || report.edges_malformed != 0
        || report.edges_skipped_dangling != 0
    {
        return Err(boxed_error(format!(
            "fixture import report is not exact: {report:?}"
        )));
    }
    let mut coactivation_indices: Vec<usize> = (0..fixture.coactivations.len()).collect();
    if reverse {
        coactivation_indices.reverse();
    }
    for index in coactivation_indices {
        let edge = &fixture.coactivations[index];
        let keys = vec![edge.key_a.clone(), edge.key_b.clone()];
        for _ in 0..edge.count {
            store.record_coactivation(&keys, None).await?;
        }
    }
    Ok(store)
}

async fn telemetry(
    store: &SqliteStore,
    key: &str,
) -> Result<(i64, u64), Box<dyn std::error::Error>> {
    match store.memory_peek(key).await? {
        MemoryPeekResult::Present { record } => Ok((record.last_accessed_at, record.access_count)),
        other => Err(boxed_error(format!(
            "expected live record {key}, got {other:?}"
        ))),
    }
}

fn keys_from_hits(hits: &[ab_store::MemorySearchHit]) -> Vec<String> {
    hits.iter().map(|hit| hit.record.key.clone()).collect()
}

async fn observe(
    store: &SqliteStore,
    fixture: &Fixture,
) -> Result<Observation, Box<dyn std::error::Error>> {
    let before = telemetry(store, "graph_neighbor_0").await?;
    let options = MemorySearchReferenceOptions {
        as_of_secs: fixture.as_of_secs,
        graph_fanout: fixture.graph_fanout,
        max_context_bytes: fixture.max_context_bytes,
        exclude_kinds: fixture.exclude_kinds.clone(),
        coactivation_rerank: true,
    };
    let seed_context = store
        .memory_search_reference(
            &fixture.query,
            &[],
            fixture.limit,
            fixture.rrf_k,
            fixture.expand_top,
            options.clone(),
        )
        .await?;
    let repeated_context = store
        .memory_search_reference(
            &fixture.query,
            &[],
            fixture.limit,
            fixture.rrf_k,
            fixture.expand_top,
            options.clone(),
        )
        .await?;
    if seed_context != repeated_context {
        return Err(boxed_error("repeated frozen reference projection changed"));
    }
    if seed_context.context_bytes != seed_context.context_json.len()
        || seed_context.context_bytes > fixture.max_context_bytes
        || seed_context.context_json.contains("access_count")
        || seed_context.context_json.contains("last_accessed_at")
        || seed_context.context_json.contains("score")
        || seed_context.hits.iter().any(|hit| hit.kind == "skill")
    {
        return Err(boxed_error(
            "reference projection violated its stable context contract",
        ));
    }

    let tie_order = keys_from_hits(
        &store
            .memory_search_as_of("tie anchor phrase", &[], fixture.limit, fixture.as_of_secs)
            .await?,
    );
    let mut before_boundary_options = options.clone();
    before_boundary_options.as_of_secs = fixture.as_of_secs - 1;
    let ttl_before_boundary_order = store
        .memory_search_reference(
            "ttl-boundary",
            &[],
            fixture.limit,
            fixture.rrf_k,
            fixture.expand_top,
            before_boundary_options,
        )
        .await?
        .hits
        .into_iter()
        .map(|hit| hit.key)
        .collect();
    let ttl_at_boundary_order = store
        .memory_search_reference(
            "ttl-boundary",
            &[],
            fixture.limit,
            fixture.rrf_k,
            fixture.expand_top,
            options.clone(),
        )
        .await?
        .hits
        .into_iter()
        .map(|hit| hit.key)
        .collect();
    let mut baseline_options = options;
    baseline_options.coactivation_rerank = false;
    let baseline_keys: Vec<String> = store
        .memory_search_reference(
            &fixture.query,
            &[],
            fixture.limit,
            fixture.rrf_k,
            fixture.expand_top,
            baseline_options,
        )
        .await?
        .hits
        .into_iter()
        .map(|hit| hit.key)
        .collect();
    let seed_keys: Vec<String> = seed_context
        .hits
        .iter()
        .map(|hit| hit.key.clone())
        .collect();
    let after = telemetry(store, "graph_neighbor_0").await?;
    Ok(Observation {
        seed_context,
        tie_order,
        ttl_before_boundary_order,
        ttl_at_boundary_order,
        telemetry_unchanged: before == after,
        coactivation_rerank_changed_order: seed_keys != baseline_keys,
    })
}

fn validate_observation(
    observation: &Observation,
    fixture: &Fixture,
) -> Result<(), Box<dyn std::error::Error>> {
    let seed_keys: Vec<String> = observation
        .seed_context
        .hits
        .iter()
        .map(|hit| hit.key.clone())
        .collect();
    if seed_keys != fixture.expected.seed_context_keys {
        return Err(boxed_error(format!(
            "seed context order drifted: {seed_keys:?}"
        )));
    }
    if observation.tie_order != fixture.expected.tie_order {
        return Err(boxed_error(format!(
            "equal-score tie order drifted: {:?}",
            observation.tie_order
        )));
    }
    if observation.ttl_before_boundary_order != fixture.expected.ttl_before_boundary_keys {
        return Err(boxed_error(format!(
            "TTL pre-boundary order drifted: {:?}",
            observation.ttl_before_boundary_order
        )));
    }
    if observation.ttl_at_boundary_order != fixture.expected.ttl_at_boundary_keys {
        return Err(boxed_error(format!(
            "TTL at-boundary order drifted: {:?}",
            observation.ttl_at_boundary_order
        )));
    }
    if !observation.telemetry_unchanged {
        return Err(boxed_error("reference graph read changed access telemetry"));
    }
    if !observation.coactivation_rerank_changed_order {
        return Err(boxed_error(
            "coactivation control did not exercise a reference order change",
        ));
    }
    Ok(())
}

fn print_receipt(observation: &Observation, fixture: &Fixture, clone_count: usize) {
    let seed_keys: Vec<String> = observation
        .seed_context
        .hits
        .iter()
        .map(|hit| hit.key.clone())
        .collect();
    println!("schema\t{SCHEMA}");
    println!("fixture_only\ttrue");
    println!("real_capture_authorized\tfalse");
    println!("clone_count\t{clone_count}");
    println!("fresh_clone_projection_equal\ttrue");
    println!("seed_context_keys\t{}", seed_keys.join(","));
    println!("tie_order\t{}", observation.tie_order.join(","));
    println!(
        "ttl_before_boundary_order\t{}",
        observation.ttl_before_boundary_order.join(",")
    );
    println!(
        "ttl_at_boundary_order\t{}",
        observation.ttl_at_boundary_order.join(",")
    );
    println!("graph_fanout\t{}", fixture.graph_fanout);
    println!("excluded_skill\ttrue");
    println!(
        "access_telemetry_unchanged\t{}",
        observation.telemetry_unchanged
    );
    println!("context_budget_basis\tUTF8_BYTES_V0");
    println!("context_bytes\t{}", observation.seed_context.context_bytes);
    println!("context_budget_ok\ttrue");
    println!("volatile_fields_in_context\tfalse");
    println!("as_of_replay_equal\ttrue");
    println!("coactivation_order_invariant\ttrue");
    println!("coactivation_rerank_changed_order\ttrue");
    println!("model_tokenizer_bound\tfalse");
    println!("runtime_influence\tfalse");
    println!("decision\tBLOCKED_FAIL_CLOSED");
    println!(
        "sentinels_cleared\t{}",
        SENTINEL_ENVS
            .iter()
            .all(|name| std::env::var_os(name).is_none())
    );
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fixture_path = std::env::args()
        .nth(1)
        .ok_or("usage: memory_reference_admission_fixture <fixture.json>")?;
    let fixture: Fixture = serde_json::from_str(&tokio::fs::read_to_string(&fixture_path).await?)?;
    validate_fixture(&fixture)?;

    let temp_root = std::env::temp_dir().join(format!(
        "ab-reference-admission-fixture-{}",
        std::process::id()
    ));
    if tokio::fs::try_exists(&temp_root).await? {
        tokio::fs::remove_dir_all(&temp_root).await?;
    }
    tokio::fs::create_dir_all(&temp_root).await?;

    let mut observations = Vec::new();
    for (index, reverse) in [false, true, true].into_iter().enumerate() {
        let clone_root = temp_root.join(format!("clone-{index}"));
        let store = build_clone(&clone_root, &fixture, reverse).await?;
        let observation = observe(&store, &fixture).await?;
        validate_observation(&observation, &fixture)?;
        observations.push(observation);
    }

    if observations.windows(2).any(|pair| pair[0] != pair[1]) {
        return Err(boxed_error("fresh clone observations are not byte-stable"));
    }
    let observation = observations
        .into_iter()
        .next()
        .ok_or("fixture did not produce an observation")?;
    print_receipt(&observation, &fixture, 3);
    tokio::fs::remove_dir_all(&temp_root).await?;
    Ok(())
}
